import abc
import errno
import logging
import os
import platform
import select
import selectors
import socket
import time
from abc import ABC
from typing import Optional, BinaryIO

from serial import Serial, PARITY_ODD, PARITY_NONE, SerialException


class ConnectFailed(BaseException):
    def __init__(self, message: str):
        super().__init__(message)


class DisconnectFailed(BaseException):
    def __init__(self, message: str):
        super().__init__(message)


class CannotReadFromPrinter(BaseException):
    def __init__(self, message: str):
        super().__init__(message)


class CannotWriteToPrinter(BaseException):
    def __init__(self, message: str):
        super().__init__(message)


# Used to mark the end of file. The consumer only needs to understand strings and not special None/empty values.
class EndOfFile(BaseException):
    pass


class PrinterConnection(ABC):
    _GENERIC_DISCONNECT_MESSAGE = "Can't read from printer (disconnected?)"

    @abc.abstractmethod
    def connect(self):
        pass

    @abc.abstractmethod
    def disconnect(self):
        pass

    @abc.abstractmethod
    def reset(self):
        pass

    @abc.abstractmethod
    def write(self, command: str):
        pass

    @abc.abstractmethod
    def read(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def uses_checksum(self):
        pass

    @property
    @abc.abstractmethod
    def can_listen(self):
        pass


class SerialConnection(PrinterConnection):
    def __init__(self, port: str, baud: int):
        # Not all platforms need to do this parity workaround, and some drivers
        # don't support it.  Limit it to platforms that actually require it
        # here to avoid doing redundant work elsewhere and potentially breaking
        # things.
        self._needs_parity_workaround = platform.system() == "linux" and os.path.exists("/etc/debian")
        self._port: str = port
        self._baud: int = baud
        self._printer: Optional[Serial] = None

        self._logger = logging.getLogger('SerialConnection')
        self._logger.setLevel(level=logging.DEBUG)

        # create formatter and add it to the handlers
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh = logging.FileHandler('/home/pi/serial.log')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        self._logger.addHandler(fh)

    def _set_hup(self, should_disable: bool):
        if platform.system() == "Linux":
            if should_disable:
                os.system(f"stty -F {self._port} -hup")
            else:
                os.system(f"stty -F {self._port} hup")

    def connect(self):
        self._logger.info("Connecting!")
        try:
            self._set_hup(True)

            if self._needs_parity_workaround:
                self._printer = Serial(port=self._port,
                                       baudrate=self._baud,
                                       timeout=0.25,
                                       parity=PARITY_ODD)
                self._printer.close()
                self._printer.parity = PARITY_NONE
            else:
                self._printer = Serial(baudrate=self._baud,
                                       timeout=0.25,
                                       parity=PARITY_NONE)
                self._printer.port = self._port

            self._printer.open()
        except (SerialException, IOError) as ex:
            message = f"Could not connect to {self._port} at baudrate {self._baud}"

            raise ConnectFailed(message) from ex

    def disconnect(self):
        if self._printer is None:
            return
        self._logger.info("Disconnecting!")
        try:
            self._printer.close()
            self._printer = None
        except OSError as ex:
            raise DisconnectFailed(f"Serial disconnect failed for {self._port}") from ex

    def reset(self):
        if self._printer is not None:
            self._printer.dtr = 1
            time.sleep(0.1)
            self._printer.dtr = 0

    def write(self, command: str):
        try:
            self._logger.debug(f">>> {command.rstrip()}")
            self._printer.write(command.encode('utf-8'))
        except SerialException as ex:
            raise CannotWriteToPrinter("Serial exception on write") from ex

    def read(self) -> str:
        try:
            line_bytes = self._printer.readline()
            if line_bytes is None:
                raise EndOfFile()

            result = line_bytes.decode('utf-8')
            if result.rstrip():
                self._logger.debug(f"<<< {result.rstrip()}")
            return result
        except UnicodeDecodeError as ex:
            message = f"Got rubbish reply from {self._port} at baudrate {self._baud}"

            raise CannotReadFromPrinter(message) from ex
        except SerialException as ex:
            raise CannotReadFromPrinter(self._GENERIC_DISCONNECT_MESSAGE) from ex
        except OSError as ex:
            if ex.errno == errno.EAGAIN:  # Not a real error, no data was available
                return ""
            raise CannotReadFromPrinter(self._GENERIC_DISCONNECT_MESSAGE) from ex

    @property
    def uses_checksum(self):
        return True

    def can_listen(self):
        return self._printer is not None and self._printer.is_open


class TcpConnection(PrinterConnection):
    _select_timeout = 0.25

    def __init__(self, host: str, port: int):
        self._host = host
        self._port = port

        self._socket: Optional[socket.socket] = None
        self._printer: Optional[BinaryIO] = None
        self._selector: Optional[selectors.SelectSelector] = None
        self._readline_buff_string = ""
        self._eof = False

    def connect(self):
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(1.0)
            self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            # a single read timeout raises OSError for all later reads
            # probably since python 3.5
            # use non blocking instead
            self._socket.settimeout(0)
            self._socket.connect((self._host, self._port))

            self._printer = self._socket.makefile('rwb', buffering=0)
            self._selector = selectors.DefaultSelector()
            self._selector.register(self._socket, selectors.EVENT_READ)
            self._eof = False
        except socket.error as ex:
            message = f"Could not connect to {self._host}:{self._port}"

            self._socket = None
            self._printer = None
            self._selector = None  # Unsure about this one

            raise ConnectFailed(message) from ex

    def disconnect(self):
        try:
            if self._selector is not None:
                self._selector.unregister(self._socket)
                self._selector.close()
                self._selector = None

            if self._socket is not None:
                self._socket.close()
                self._socket = None

            self._printer.close()
            self._printer = None
        except socket.error as ex:
            message = f"Could not disconnect from {self._host}:{self._port}"

            raise ConnectFailed(message) from ex

    def reset(self):
        pass  # Nothing to do

    def write(self, command: str):
        try:
            self._printer.write(command.encode('utf-8'))
            self._printer.flush()
        except socket.timeout:
            pass
        except socket.error as ex:
            raise CannotWriteToPrinter("Socket error on write") from ex
        except RuntimeError as ex:
            raise CannotWriteToPrinter("Socket connection broken") from ex

    def _readline_buf(self) -> str:
        """Try to readline from buffer"""
        if '\n' in self._readline_buff_string:
            eol_index = self._readline_buff_string.find('\n')

            line = self._readline_buff_string[:eol_index + 1]
            self._readline_buff_string = self._readline_buff_string[eol_index + 1:]
            return line
        elif self._eof:  # EOF, return whatever we have
            line = self._readline_buff_string
            self._readline_buff_string = ""
            return line

        return ''

    def _readline_nb(self) -> str:
        chunk_size = 256

        while True:
            line = self._readline_buf()
            if line:
                return line

            if self._eof:
                raise EndOfFile()

            # Try to read data immediately
            chunk: bytes = self._printer.read(chunk_size)
            # If that returns no data, try to read again up to our timeout
            if chunk is None and self._selector.select(self._select_timeout):
                chunk = self._printer.read(chunk_size)

            if chunk is None:  # No data, return empty string
                return ''
            elif chunk == b'':  # EOF
                # Setting the eof flag and returning no data allows us to raise EOF after all of the lines have been
                # consumed.
                self._eof = True
                continue
            else:
                self._readline_buff_string += chunk.decode('utf-8')
                continue

    def read(self) -> str:
        try:
            return self._readline_nb()
        except socket.error as ex:
            raise CannotReadFromPrinter(self._GENERIC_DISCONNECT_MESSAGE) from ex
        except (OSError, select.error) as ex:
            # OSError and select.error are the same thing since python 3.3
            if len(ex.args) > 1 and 'Bad file descriptor' in ex.args[1]:
                raise CannotReadFromPrinter(self._GENERIC_DISCONNECT_MESSAGE) from ex
            else:
                raise CannotReadFromPrinter("SelectError") from ex

    @property
    def uses_checksum(self):
        return False  # TCP handles checksum

    def can_listen(self):
        return self._printer is not None


@property
def uses_checksum(self):
    return False
