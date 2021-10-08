import time

from bqclient.host.drivers.printrun.connection import SerialConnection
from bqclient.host.drivers.printrun.printcore import PrintCore
from bqclient.host.drivers.printrun.gcoder import LightGCode


class PrintrunDriver(object):
    def __init__(self, config):
        self.serial_port = config["connection"]["port"]
        self.baud_rate = None

        if "baud" in config["connection"]:
            self.baud_rate = config["connection"]["baud"]

        self.printcore = PrintCore()

    def connect(self):
        serial_connection = SerialConnection(self.serial_port, self.baud_rate)
        self.printcore.connect(serial_connection)

        while not self.printcore.online:
            print("Printer is not online yet")
            time.sleep(2)

    def disconnect(self):
        self.printcore.disconnect()

    def run(self, filename, **kwargs):
        if "update_job_progress" in kwargs:
            update_job_progress = kwargs["update_job_progress"]
        else:
            update_job_progress = None

        with open(filename, 'rb') as fh:
            gcode = [i.strip().decode("utf-8") for i in fh.readlines()]

        gcode = LightGCode(gcode)

        self.printcore.startprint(gcode)

        while self.printcore.printing:
            time.sleep(5)

            progress = 100.0 * (float(self.printcore.queueindex) / float(len(self.printcore.mainqueue)))
            if update_job_progress is not None:
                update_job_progress(progress)
