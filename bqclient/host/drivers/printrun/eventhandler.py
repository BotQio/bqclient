# This file is originally from printrun, but has been modified heavily for BotQio.
# Please see the original repo here: https://github.com/kliment/Printrun
import inspect
import logging
import traceback
from typing import Iterable


class PrinterEventHandler(object):
    """
    Defines a skeleton of an event-handler for printer events. It
    allows attaching to the printcore and will be triggered for
    different events.
    """

    def on_init(self):
        """
        Called whenever a new printcore is initialized.
        """
        pass

    def on_send(self, command, gcode_line):
        """
        Called on every command sent to the printer.

        :param command: The command to be sent.
        :param gcode_line: The parsed high-level command.
        """
        pass

    def on_receive(self, line):
        """
        Called on every line read from the printer.

        :param line: The data has been read from printer.
        """
        pass

    def on_connect(self):
        """
        Called whenever printcore is connected.
        """
        pass

    def on_disconnect(self):
        """
        Called whenever printcore is disconnected.
        """
        pass

    def on_error(self, error):
        """
        Called whenever an error occurs.

        :param error: The error that has been triggered.
        """
        pass

    def on_online(self):
        """
        Called when printer comes online.
        """
        pass

    def on_temp(self, line):
        """
        Called for temp, status, whatever.

        :param line: Line of data.
        """
        pass

    def on_start(self, resume):
        """
        Called when printing is started.

        :param resume: If true, the print is resumed.
        """
        pass

    def on_end(self):
        """
        Called when printing ends.
        """
        pass

    def on_layer_change(self, layer):
        """
        Called on layer changed.

        :param layer: The new layer.
        """
        pass

    def on_pre_print_send(self, gcode_line, index, main_queue):
        """
        Called pre sending printing command.

        :param gcode_line: Line to be send.
        :param index: Index in the main queue.
        :param main_queue: The main queue of commands.
        """
        pass

    def on_print_send(self, gcode_line):
        """
        Called whenever a line is sent to the printer.

        :param gcode_line: The line send to the printer.
        """
        pass


class ProxyEventHandler(PrinterEventHandler):
    """
    This class acts as an easy interface for calling a list of event handlers. It will swallow exceptions so the main
    printcore engine doesn't have to worry about them.
    """

    def __init__(self, event_handlers: Iterable[PrinterEventHandler]):
        super().__init__()
        self._event_handlers = list(event_handlers)

    def add_handler(self, handler: PrinterEventHandler):
        self._event_handlers.append(handler)

    def _call_function(self, f, *args):
        name = f.__name__
        for handler in self._event_handlers:
            try:
                if not hasattr(handler, name):
                    continue

                attr = getattr(handler, name)
                if inspect.ismethod(attr):
                    attr(*args)
            except BaseException:
                logging.error(traceback.format_exc())

    def on_init(self):
        self._call_function(PrinterEventHandler.on_init)

    def on_send(self, command, gcode_line):
        self._call_function(PrinterEventHandler.on_send, command, gcode_line)

    def on_receive(self, line):
        self._call_function(PrinterEventHandler.on_receive, line)

    def on_connect(self):
        self._call_function(PrinterEventHandler.on_connect)

    def on_disconnect(self):
        self._call_function(PrinterEventHandler.on_disconnect)

    def on_error(self, error):
        self._call_function(PrinterEventHandler.on_error, error)

    def on_online(self):
        self._call_function(PrinterEventHandler.on_online)

    def on_temp(self, line):
        self._call_function(PrinterEventHandler.on_temp, line)

    def on_start(self, resume):
        self._call_function(PrinterEventHandler.on_start, resume)

    def on_end(self):
        self._call_function(PrinterEventHandler.on_end)

    def on_layer_change(self, layer):
        self._call_function(PrinterEventHandler.on_layer_change, layer)

    def on_pre_print_send(self, gcode_line, index, main_queue):
        self._call_function(PrinterEventHandler.on_pre_print_send, gcode_line, index, main_queue)

    def on_print_send(self, gcode_line):
        self._call_function(PrinterEventHandler.on_print_send, gcode_line)
