# This file is originally from printrun, but has been modified heavily for BotQio.
# Please see the original repo here: https://github.com/kliment/Printrun
import re
from typing import Optional, Tuple, List

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
from bqclient.host.drivers.printrun.utils import set_utf8_locale, install_locale

try:
    set_utf8_locale()
except BaseException:
    pass
install_locale('pronterface')


def locked(f):
    @wraps(f)
    def inner(*args, **kw):
        with inner.lock:
            return f(*args, **kw)

    inner.lock = threading.Lock()
    return inner


gcode_strip_comment_exp = re.compile("\([^\(\)]*\)|;.*|[/\*].*\n")


class PrintCore(object):
    _known_greetings: Tuple[str] = ('start', 'Grbl ',)

    def __init__(self):
        self._connection: Optional[PrinterConnection] = None
        # self.analyzer = gcoder.GCode()
        # clear to send, enabled after responses
        # FIXME: should probably be changed to a sliding window approach
        self.clear_to_send = 0
        # The printer has responded to the initial command and is active
        self.online = False
        # is a print currently running, true if printing, false if paused
        self.printing = False
        self.paused = False

        self.log = deque(maxlen=10000)

        self.main_queue: Optional[List[str]] = None
        self.priority_queue = Queue(0)
        self.main_queue_index = 0
        self.line_number = 0
        self.resend_from = -1
        self.sent_lines = {}
        self.write_failures = 0

        self.read_thread = None
        self.stop_read_thread = False
        self.send_thread = None
        self.stop_send_thread = False
        self.print_thread = None

        self._event_proxy = ProxyEventHandler([])
        self._event_proxy.on_init()

        self.xy_feedrate = None
        self.z_feedrate = None

        self.pause_x_coordinate = None
        self.pause_y_coordinate = None
        self.pause_z_coordinate = None
        self.pause_e_coordinate = None
        self.pause_f_coordinate = None
        self.relative_pause = None
        self.relative_pause_e = None

    def add_event_handler(self, handler: PrinterEventHandler):
        """
        Adds an event handler.

        :param handler: The handler to be added.
        """
        self._event_proxy.add_handler(handler)

    def log_error(self, error):
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
            self.log_error("Exception occurred due to cannot read from printer!")
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
                    if empty_lines == 15:
                        break
                else:
                    empty_lines = 0

                self._event_proxy.on_receive(line)

                if line.startswith(self._known_greetings) \
                        or line.startswith('ok') or "T:" in line:
                    self.online = True
                    self._event_proxy.on_online()
                    return

    def _listen(self):
        """This function acts on messages from the firmware"""
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

            if line.rstrip():
                self._event_proxy.on_receive(line.rstrip())

            if line.startswith('DEBUG_'):
                continue
            if line.startswith(self._known_greetings) or line.startswith('ok'):
                self.clear_to_send = True
            if line.startswith('ok') and "T:" in line:
                self._event_proxy.on_temp(line)
            elif line.startswith('Error'):
                self.log_error(line)
            # Test strings for resend parsing       # Firmware     exp. result
            # line="rs N2 Expected checksum 67"    # Teacup       2
            if line.lower().startswith("resend") or line.startswith("rs"):
                for haystack in ["N:", "N", ":"]:
                    line = line.replace(haystack, " ")
                line_words = line.split()
                while len(line_words) != 0:
                    try:
                        to_resend = int(line_words.pop(0))
                        self.resend_from = to_resend
                        break
                    except BaseException:
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
                command = self.priority_queue.get(True, 0.1)
            except QueueEmpty:
                continue
            while self._connection is not None and self.printing and not self.clear_to_send:
                time.sleep(0.001)
            self._send(command)
            while self._connection is not None and self.printing and not self.clear_to_send:
                time.sleep(0.001)

    @staticmethod
    def _checksum(command):
        return reduce(lambda x, y: x ^ y, map(ord, command))

    def start_print(self, gcode: List[str]):
        """Start a print, gcode is an array of gcode commands.
        returns True on success, False if already printing.
        The print queue will be replaced with the contents of the data array,
        the next line will be set to 0 and the firmware notified. Printing
        will then start in a parallel thread.
        """
        if self.printing or not self.online or self._connection is None:
            return False
        self.main_queue_index = 0
        self.main_queue = gcode
        self.printing = True
        self.line_number = 0
        self.resend_from = -1
        if not gcode:
            return True

        self.clear_to_send = False
        self._send("M110", -1, True)

        self.print_thread = threading.Thread(target=self._print,
                                             name='print thread',
                                             kwargs={"resuming": False})
        self.print_thread.start()
        return True

    # TODO Re-enable more detailed print control
    # def cancel_print(self):
    #     self.pause()
    #     self.paused = False
    #     self.main_queue = None
    #     self.clear_to_send = True
    #
    # def pause(self):
    #     """Pauses the print, saving the current position.
    #     """
    #     if not self.printing:
    #         return False
    #     self.paused = True
    #     self.printing = False
    #
    #     # ';@pause' in the gcode file calls pause from the print thread
    #     if not threading.current_thread() is self.print_thread:
    #         try:
    #             self.print_thread.join()
    #         except BaseException:
    #             self.log_error(traceback.format_exc())
    #
    #     self.print_thread = None
    #
    #     # saves the status
    #     self.pause_x_coordinate = self.analyzer.abs_x
    #     self.pause_y_coordinate = self.analyzer.abs_y
    #     self.pause_z_coordinate = self.analyzer.abs_z
    #     self.pause_e_coordinate = self.analyzer.abs_e
    #     self.pause_f_coordinate = self.analyzer.current_f
    #     self.relative_pause = self.analyzer.relative
    #     self.relative_pause_e = self.analyzer.relative_e
    #
    # def resume(self):
    #     """Resumes a paused print."""
    #     if not self.paused:
    #         return False
    #     # restores the status
    #     self.send_now("G90")  # go to absolute coordinates
    #
    #     xy_feedrate = '' if self.xy_feedrate is None else ' F' + str(self.xy_feedrate)
    #     z_feedrate = '' if self.z_feedrate is None else ' F' + str(self.z_feedrate)
    #
    #     self.send_now("G1 X%s Y%s%s" % (self.pause_x_coordinate, self.pause_y_coordinate, xy_feedrate))
    #     self.send_now("G1 Z" + str(self.pause_z_coordinate) + z_feedrate)
    #     self.send_now("G92 E" + str(self.pause_e_coordinate))
    #
    #     # go back to relative if needed
    #     if self.relative_pause:
    #         self.send_now("G91")
    #     if self.relative_pause_e:
    #         self.send_now('M83')
    #     # reset old feed rate
    #     self.send_now("G1 F" + str(self.pause_f_coordinate))
    #
    #     self.paused = False
    #     self.printing = True
    #     self.print_thread = threading.Thread(target=self._print,
    #                                          name='print thread',
    #                                          kwargs={"resuming": True})
    #     self.print_thread.start()

    def send(self, command):
        """Adds a command to the main command queue if printing, or sends the command immediately if not printing"""

        if self.online:
            if self.printing:
                self.main_queue.append(command)
            else:
                self.priority_queue.put_nowait(command)
        else:
            self.log_error(_("Not connected to printer."))

    def send_now(self, command):
        """Sends a command to the printer ahead of the command queue"""
        if self.online:
            self.priority_queue.put_nowait(command)
        else:
            self.log_error(_("Not connected to printer."))

    def _print(self, resuming=False):
        self._stop_sender()
        try:
            self._event_proxy.on_start(resuming)
            while self.printing and self._connection is not None and self.online:
                self._send_next()
            self.sent_lines = {}
            self.log.clear()
            self.sent = []
            self._event_proxy.on_end()
        except BaseException:
            self.log_error(_("Print thread died due to the following error:") +
                           "\n" + traceback.format_exc())
        finally:
            self.print_thread = None
            self._start_sender()

    def process_host_command(self, command):
        command = command.lstrip()
        # if command.startswith(";@pause"):
        #     self.pause()

    def _send_next(self):
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
        if self.line_number > self.resend_from > -1:
            self._send(self.sent_lines[self.resend_from], self.resend_from, False)
            self.resend_from += 1
            return
        self.resend_from = -1
        if not self.priority_queue.empty():
            self._send(self.priority_queue.get_nowait())
            self.priority_queue.task_done()
            return
        if self.printing and 0 <= self.main_queue_index < len(self.main_queue):
            raw_gcode_line = self.main_queue[self.main_queue_index]
            # if self.main_queue_index > 0:
            #     (prev_layer, prev_line) = self.main_queue.idxs(self.main_queue_index - 1)
            #     if prev_layer != layer:
            #         self._event_proxy.on_layer_change(layer)
            # self._event_proxy.on_pre_print_send(gcode_line, self.main_queue_index, self.main_queue)
            if raw_gcode_line is None:
                self.main_queue_index += 1
                self.clear_to_send = True
                return

            if raw_gcode_line.lstrip().startswith(";@"):  # check for host command
                self.process_host_command(raw_gcode_line)
                self.main_queue_index += 1
                self.clear_to_send = True
                return

            # Strip comments
            raw_gcode_line = gcode_strip_comment_exp.sub("", raw_gcode_line).strip()
            if raw_gcode_line:
                self._send(raw_gcode_line, self.line_number, True)
                self.line_number += 1
                # self._event_proxy.on_print_send(gcode_line)
            else:
                self.clear_to_send = True
            self.main_queue_index += 1
        else:
            self.printing = False
            self.clear_to_send = True
            if not self.paused:
                self.main_queue_index = 0
                self.line_number = 0
                self._send("M110", -1, True)

    def _send(self, command, lineno=0, calculate_checksum=False):
        # Only add checksums if over serial (tcp does the flow control itself)
        if calculate_checksum and self._connection.uses_checksum:
            prefix = "N" + str(lineno) + " " + command
            command = prefix + "*" + str(self._checksum(prefix))
            if "M110" not in command:
                self.sent_lines[lineno] = command
        if self._connection:
            # run the command through the analyzer
            gcode_line = None
            # try:
            #     gcode_line = self.analyzer.append(command, store=False)
            # except BaseException:
            #     logging.warning(_("Could not analyze command %s:") % command +
            #                     "\n" + traceback.format_exc())

            self._event_proxy.on_send(command, gcode_line)
            try:
                self._connection.write(f"{command}\n")
                self.write_failures = 0
            except CannotWriteToPrinter:
                # TODO Log the error
                self.write_failures += 1
