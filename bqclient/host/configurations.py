from bqclient.host.framework.configuration import Configuration
from bqclient.host.framework.ioc import singleton


@singleton
class HostConfiguration(Configuration):
    def __init__(self):
        super(HostConfiguration, self).__init__('host')

    @staticmethod
    def _default_config():
        return {
            'servers': {}
        }
