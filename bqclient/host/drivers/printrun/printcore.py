# This file is originally from printrun, but has been modified heavily for BotQio.
# Please see the original repo here: https://github.com/kliment/Printrun

from typing import Optional

from bqclient.host.drivers.printrun.connection import PrinterConnection, CannotWriteToPrinter, CannotReadFromPrinter, \
    EndOfFile
from bqclient.host.drivers.printrun.eventhandler import PrinterEventHandler, ProxyEventHandler

import threading
from queue import Queue, Empty as QueueEmpty
import time
import logging
import traceback
from functools import wraps, reduce
from collections import deque
from bqclient.host.drivers.printrun import gcoder
from bqclient.host.drivers.printrun.utils import set_utf8_locale, install_locale

try:
    set_utf8_locale()
except:
    pass
install_locale('pronterface')


def locked(f):
    @wraps(f)
    def inner(*args, **kw):
        with inner.lock:
            return f(*args, **kw)

    inner.lock = threading.Lock()
    return inner


PR_EOF = None  # printrun's marker for EOF
PR_AGAIN = b''  # printrun's marker for timeout/no data
SYS_EOF = b''  # python's marker for EOF
SYS_AGAIN = None  # python's marker for timeout/no data


class PrintCore(object):
    def __init__(self):
        self._connection: Optional[PrinterConnection] = None
        self.analyzer = gcoder.GCode()
        # clear to send, enabled after responses
        # FIXME: should probably be changed to a sliding window approach
        self.clear_to_send = 0
        # The printer has responded to the initial command and is active
        self.online = False
        # is a print currently running, true if printing, false if paused
        self.printing = False
        self.mainqueue = None
        self.priqueue = Queue(0)
        self.queueindex = 0
        self.lineno = 0
        self.resendfrom = -1
        self.paused = False
        self.sentlines = {}
        self.log = deque(maxlen=10000)
        self.sent = []
        self.write_failures = 0
        self.greetings = ['start', 'Grbl ']
        self.wait = 0  # default wait period for send(), send_now()
        self.read_thread = None
        self.stop_read_thread = False
        self.send_thread = None
        self.stop_send_thread = False
        self.print_thread = None
        self.readline_buf = []
        self.selector = None
        self._event_proxy = ProxyEventHandler([])
        self._event_proxy.on_init()
        self.xy_feedrate = None
        self.z_feedrate = None

    def add_event_handler(self, handler: PrinterEventHandler):
        """
        Adds an event handler.

        :param handler: The handler to be added.
        """
        self._event_proxy.add_handler(handler)

    def logError(self, error):
        self._event_proxy.on_error(error)

    @locked
    def disconnect(self):
        """Disconnects from printer and pauses the print
        """
        if self._connection:
            if self.read_thread:
                self.stop_read_thread = True
                if threading.current_thread() != self.read_thread:
                    self.read_thread.join()
                self.read_thread = None
            if self.print_thread:
                self.printing = False
                self.print_thread.join()
            self._stop_sender()
            self._connection.disconnect()
        self._event_proxy.on_disconnect()
        self.online = False
        self.printing = False

    @locked
    def connect(self, connection: PrinterConnection):
        if self._connection:
            self.disconnect()

        self._connection = connection
        self._connection.connect()
        self._event_proxy.on_connect()
        self.stop_read_thread = False
        self.read_thread = threading.Thread(target=self._listen,
                                            name='read thread')
        self.read_thread.start()
        self._start_sender()

    def reset(self):
        if self._connection:
            self._connection.reset()

    def _readline(self) -> str:
        try:
            return self._connection.read()
        except CannotReadFromPrinter:
            self.logError("Exception occurred due to cannot read from printer!")
            raise
            # self.logException(ex)  # Need to determine exactly how this works in the calling function

    def _listen_can_continue(self):
        return self._connection is not None and not self.stop_read_thread and self._connection.can_listen

    def _listen_until_online(self):
        while not self.online and self._listen_can_continue():
            self._send("M105")
            if self.write_failures >= 4:
                logging.error(_("Aborting connection attempt after 4 failed writes."))
                return
            empty_lines = 0
            while self._listen_can_continue():
                line = self._readline()
                # workaround cases where M105 was sent before printer Serial
                # was online an empty line means read timeout was reached,
                # meaning no data was received thus we count those empty lines,
                # and once we have seen 15 in a row, we just break and send a
                # new M105
                # 15 was chosen based on the fact that it gives enough time for
                # Gen7 bootloader to time out, and that the non received M105
                # issues should be quite rare so we can wait for a long time
                # before resending
                if not line:
                    empty_lines += 1
                    if empty_lines == 15: break
                else:
                    empty_lines = 0
                if line.startswith(tuple(self.greetings)) \
                        or line.startswith('ok') or "T:" in line:
                    self.online = True
                    self._event_proxy.on_online()
                    return

    def _listen(self):
        """This function acts on messages from the firmware
        """
        self.clear_to_send = True
        if not self.printing:
            self._listen_until_online()
        while self._listen_can_continue():
            try:
                line = self._readline()
            except EndOfFile:
                self.stop_send_thread = True
                logging.debug('_readline() hit EOF')
                break

            if line.startswith('DEBUG_'):
                continue
            if line.startswith(tuple(self.greetings)) or line.startswith('ok'):
                self.clear_to_send = True
            if line.startswith('ok') and "T:" in line:
                self._event_proxy.on_temp(line)
            elif line.startswith('Error'):
                self.logError(line)
            # Teststrings for resend parsing       # Firmware     exp. result
            # line="rs N2 Expected checksum 67"    # Teacup       2
            if line.lower().startswith("resend") or line.startswith("rs"):
                for haystack in ["N:", "N", ":"]:
                    line = line.replace(haystack, " ")
                linewords = line.split()
                while len(linewords) != 0:
                    try:
                        toresend = int(linewords.pop(0))
                        self.resendfrom = toresend
                        break
                    except:
                        pass
                self.clear_to_send = True
        self.clear_to_send = True
        logging.debug('Exiting read thread')

    def _start_sender(self):
        self.stop_send_thread = False
        self.send_thread = threading.Thread(target=self._sender,
                                            name='send thread')
        self.send_thread.start()

    def _stop_sender(self):
        if self.send_thread:
            self.stop_send_thread = True
            self.send_thread.join()
            self.send_thread = None

    def _sender(self):
        while not self.stop_send_thread:
            try:
                command = self.priqueue.get(True, 0.1)
            except QueueEmpty:
                continue
            while self._connection is not None and self.printing and not self.clear_to_send:
                time.sleep(0.001)
            self._send(command)
            while self._connection is not None and self.printing and not self.clear_to_send:
                time.sleep(0.001)

    def _checksum(self, command):
        return reduce(lambda x, y: x ^ y, map(ord, command))

    def startprint(self, gcode, startindex=0):
        """Start a print, gcode is an array of gcode commands.
        returns True on success, False if already printing.
        The print queue will be replaced with the contents of the data array,
        the next line will be set to 0 and the firmware notified. Printing
        will then start in a parallel thread.
        """
        if self.printing or not self.online or self._connection is None:
            return False
        self.queueindex = startindex
        self.mainqueue = gcode
        self.printing = True
        self.lineno = 0
        self.resendfrom = -1
        if not gcode or not gcode.lines:
            return True

        self.clear_to_send = False
        self._send("M110", -1, True)

        resuming = (startindex != 0)
        self.print_thread = threading.Thread(target=self._print,
                                             name='print thread',
                                             kwargs={"resuming": resuming})
        self.print_thread.start()
        return True

    def cancelprint(self):
        self.pause()
        self.paused = False
        self.mainqueue = None
        self.clear_to_send = True

    # run a simple script if it exists, no multithreading
    def runSmallScript(self, filename):
        if not filename: return
        try:
            with open(filename) as f:
                for i in f:
                    l = i.replace("\n", "")
                    l = l.partition(';')[0]  # remove comments
                    self.send_now(l)
        except:
            pass

    def pause(self):
        """Pauses the print, saving the current position.
        """
        if not self.printing: return False
        self.paused = True
        self.printing = False

        # ';@pause' in the gcode file calls pause from the print thread
        if not threading.current_thread() is self.print_thread:
            try:
                self.print_thread.join()
            except:
                self.logError(traceback.format_exc())

        self.print_thread = None

        # saves the status
        self.pauseX = self.analyzer.abs_x
        self.pauseY = self.analyzer.abs_y
        self.pauseZ = self.analyzer.abs_z
        self.pauseE = self.analyzer.abs_e
        self.pauseF = self.analyzer.current_f
        self.pauseRelative = self.analyzer.relative
        self.pauseRelativeE = self.analyzer.relative_e

    def resume(self):
        """Resumes a paused print."""
        if not self.paused: return False
        # restores the status
        self.send_now("G90")  # go to absolute coordinates

        xyFeed = '' if self.xy_feedrate is None else ' F' + str(self.xy_feedrate)
        zFeed = '' if self.z_feedrate is None else ' F' + str(self.z_feedrate)

        self.send_now("G1 X%s Y%s%s" % (self.pauseX, self.pauseY, xyFeed))
        self.send_now("G1 Z" + str(self.pauseZ) + zFeed)
        self.send_now("G92 E" + str(self.pauseE))

        # go back to relative if needed
        if self.pauseRelative:
            self.send_now("G91")
        if self.pauseRelativeE:
            self.send_now('M83')
        # reset old feed rate
        self.send_now("G1 F" + str(self.pauseF))

        self.paused = False
        self.printing = True
        self.print_thread = threading.Thread(target=self._print,
                                             name='print thread',
                                             kwargs={"resuming": True})
        self.print_thread.start()

    def send(self, command, wait=0):
        """Adds a command to the checksummed main command queue if printing, or
        sends the command immediately if not printing"""

        if self.online:
            if self.printing:
                self.mainqueue.append(command)
            else:
                self.priqueue.put_nowait(command)
        else:
            self.logError(_("Not connected to printer."))

    def send_now(self, command, wait=0):
        """Sends a command to the printer ahead of the command queue, without a
        checksum"""
        if self.online:
            self.priqueue.put_nowait(command)
        else:
            self.logError(_("Not connected to printer."))

    def _print(self, resuming=False):
        self._stop_sender()
        try:
            self._event_proxy.on_start(resuming)
            while self.printing and self._connection is not None and self.online:
                self._sendnext()
            self.sentlines = {}
            self.log.clear()
            self.sent = []
            self._event_proxy.on_end()
        except:
            self.logError(_("Print thread died due to the following error:") +
                          "\n" + traceback.format_exc())
        finally:
            self.print_thread = None
            self._start_sender()

    def process_host_command(self, command):
        """only ;@pause command is implemented as a host command in printcore, but hosts are free to reimplement this method"""
        command = command.lstrip()
        if command.startswith(";@pause"):
            self.pause()

    def _sendnext(self):
        if self._connection is None:
            return
        while self._connection is not None and self.printing and not self.clear_to_send:
            time.sleep(0.001)
        # Only wait for oks when using serial connections or when not using tcp
        # in streaming mode:
        self.clear_to_send = False
        if not (self.printing and self._connection is not None and self.online):
            self.clear_to_send = True
            return
        if self.resendfrom < self.lineno and self.resendfrom > -1:
            self._send(self.sentlines[self.resendfrom], self.resendfrom, False)
            self.resendfrom += 1
            return
        self.resendfrom = -1
        if not self.priqueue.empty():
            self._send(self.priqueue.get_nowait())
            self.priqueue.task_done()
            return
        if self.printing and self.mainqueue.has_index(self.queueindex):
            (layer, line) = self.mainqueue.idxs(self.queueindex)
            gline = self.mainqueue.all_layers[layer][line]
            if self.queueindex > 0:
                (prev_layer, prev_line) = self.mainqueue.idxs(self.queueindex - 1)
                if prev_layer != layer:
                    self._event_proxy.on_layer_change(layer)
            self._event_proxy.on_pre_print_send(gline, self.queueindex, self.mainqueue)
            if gline is None:
                self.queueindex += 1
                self.clear_to_send = True
                return
            tline = gline.raw
            if tline.lstrip().startswith(";@"):  # check for host command
                self.process_host_command(tline)
                self.queueindex += 1
                self.clear_to_send = True
                return

            # Strip comments
            tline = gcoder.gcode_strip_comment_exp.sub("", tline).strip()
            if tline:
                self._send(tline, self.lineno, True)
                self.lineno += 1
                self._event_proxy.on_print_send(gline)
            else:
                self.clear_to_send = True
            self.queueindex += 1
        else:
            self.printing = False
            self.clear_to_send = True
            if not self.paused:
                self.queueindex = 0
                self.lineno = 0
                self._send("M110", -1, True)

    def _send(self, command, lineno=0, calculate_checksum=False):
        # Only add checksums if over serial (tcp does the flow control itself)
        if calculate_checksum and self._connection.uses_checksum:
            prefix = "N" + str(lineno) + " " + command
            command = prefix + "*" + str(self._checksum(prefix))
            if "M110" not in command:
                self.sentlines[lineno] = command
        if self._connection:
            self.sent.append(command)
            # run the command through the analyzer
            gcode_line = None
            try:
                gcode_line = self.analyzer.append(command, store=False)
            except:
                logging.warning(_("Could not analyze command %s:") % command +
                                "\n" + traceback.format_exc())

            self._event_proxy.on_send(command, gcode_line)
            try:
                self._connection.write(f"{command}\n")
                self.write_failures = 0
            except CannotWriteToPrinter:
                # TODO Log the error
                self.write_failures += 1