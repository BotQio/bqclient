import time
from threading import Thread, Event
from typing import Optional

from bqclient.host.drivers.driver_interface import DriverInterface


class DummyDriver(DriverInterface):
    def start(self, file_path):
        self._current_file_path = file_path
        self._should_stop.clear()
        self._should_pause.clear()

        self._job_thread = Thread(target=self._run)

    def stop(self):
        self._should_stop.set()

    def __init__(self, config):
        self.command_delay = 100

        if config is not None and "command_delay" in config:
            self.command_delay = float(config["command_delay"])

        self._current_file_path: Optional[str] = None
        self._job_thread: Optional[Thread] = None
        self._should_stop: Event = Event()
        self._should_pause: Event = Event()

    def connect(self):
        self.connected_callback()

    def disconnect(self):
        self.disconnected_callback()

    def _run(self):
        with open(self._current_file_path, 'rb') as fh:
            lines = fh.readlines()

            # We get an update every 0.1%, essentially.
            update_every_x_lines = len(lines) // 1_000

            for index, line in enumerate(lines):
                print(f"Gcode: {line.strip()}")
                time.sleep(self.command_delay)

                if self._should_stop.is_set():
                    return

                if self._should_pause.is_set():
                    while self._should_pause.is_set():
                        time.sleep(1)

                        if self._should_stop.is_set():
                            return

                if index % update_every_x_lines:
                    progress = 100.0 * (float(index) / float(len(lines)))
                    self.job_progress_callback(progress)

            self.job_finished_callback()
