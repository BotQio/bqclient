from abc import abstractmethod
from typing import List

from bqclient.host.framework.recurring_task import RecurringTask


class Handler(object):
    @abstractmethod
    def tasks(self) -> List[RecurringTask]:
        pass
