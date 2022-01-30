import time
from threading import Thread
from typing import Optional

from bqclient.host.drivers.driver_interface import DriverInterface
from bqclient.host.drivers.printrun.connection import SerialConnection
from bqclient.host.drivers.printrun.handlers.log_handler import LogHandler
from bqclient.host.drivers.printrun.printcore import PrintCore


class PrintrunDriver(DriverInterface):
    def __init__(self,
                 config,
                 log_handler: LogHandler):
        self.serial_port = config["connection"]["port"]
        self.baud_rate = None

        if "baud" in config["connection"]:
            self.baud_rate = config["connection"]["baud"]

        self.printcore = PrintCore()
        self.printcore.add_event_handler(log_handler)
        self._progress_thread: Thread = Thread(target=self._run_progress, daemon=True)
        self._progress_thread.start()

    def connect(self):
        serial_connection = SerialConnection(self.serial_port, self.baud_rate)
        self.printcore.connect(serial_connection)

        while not self.printcore.online:
            print("Printer is not online yet")
            time.sleep(2)

    def disconnect(self):
        self.printcore.disconnect()

    def start(self, file_path):
        with open(file_path, 'rb') as fh:
            gcode = [i.strip().decode("utf-8") for i in fh.readlines()]

        self.printcore.start(gcode)

    def stop(self):
        # self.printcore.cancel()  # Cancel needs pause, so leave it disabled for now.
        pass

    def _run_progress(self):
        while True:
            time.sleep(60)

            while self.printcore.printing:
                time.sleep(10)

                queue_length = len(self.printcore.main_queue)
                if queue_length == 0:
                    continue

                progress = 100.0 * (float(self.printcore.main_queue_index) / float(queue_length))
                self.job_progress_callback(progress)
