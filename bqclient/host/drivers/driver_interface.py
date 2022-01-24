import abc

from bqclient.host.helpers.callback import Callback, GenericCallback


class DriverInterface(abc.ABC):
    connected_callback: Callback = Callback()
    disconnected_callback: Callback = Callback()
    job_started_callback: Callback = Callback()
    job_finished_callback: Callback = Callback()
    job_progress_callback: GenericCallback[float] = GenericCallback()

    @abc.abstractmethod
    def connect(self):  # TODO Error states?
        pass

    @abc.abstractmethod
    def disconnect(self):
        pass

    @abc.abstractmethod
    def start(self, file_path):
        pass

    @abc.abstractmethod
    def stop(self):
        pass

    # @abc.abstractmethod
    # def pause(self):
    #     pass
    #
    # @abc.abstractmethod
    # def resume(self):
    #     pass
