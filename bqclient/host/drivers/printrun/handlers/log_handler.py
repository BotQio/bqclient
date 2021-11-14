import logging
import logging.handlers
from pathlib import Path

from appdirs import AppDirs

from bqclient.host.drivers.printrun.eventhandler import PrinterEventHandler


class LogHandler(PrinterEventHandler):
    def __init__(self,
                 app_dirs: AppDirs):
        self._logger = logging.getLogger('PrintcoreLogger')
        self._logger.setLevel(level=logging.DEBUG)

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        log_file_name = Path(app_dirs.user_log_dir) / 'printcore.log'
        self._fh = logging.handlers.RotatingFileHandler(log_file_name, backupCount=10)
        self._fh.setLevel(logging.DEBUG)
        self._fh.setFormatter(formatter)
        self._logger.addHandler(self._fh)

    def on_connect(self):
        self._logger.info("Connecting!")

    def on_disconnect(self):
        self._logger.info("Disconnecting!")

    def on_send(self, command, gcode_line):
        self._logger.debug(f">>> {command}")

    def on_receive(self, line):
        self._logger.debug(f"<<< {line}")

    def on_error(self, error):
        self._logger.error(error)

    def on_start(self, resume):
        self._logger.info("Starting!")

    def on_end(self):
        self._logger.info("Ending!")
        self._fh.doRollover()
