import abc


class DriverInterface(abc.ABC):
    @abc.abstractmethod
    def connect(self):  # TODO Error states?
        pass

    @abc.abstractmethod
    def disconnect(self):
        pass

    @abc.abstractmethod
    def start(self, filename):
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
