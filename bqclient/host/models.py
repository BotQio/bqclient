from typing import TYPE_CHECKING, TypeVar, Generic, Optional

if TYPE_CHECKING:
    from bqclient.host.api.rest import RestApi


class DataCarrier(object):
    def __init__(self, data):
        self.data = data
        self.updated = {}

    def updated_or_data(self, name: str):
        return self.updated[name] if name in self.updated else self.data[name]


T = TypeVar('T')


class ReadOnlyValue(Generic[T]):
    def __init__(self, name: str):
        self._name = name

    def __get__(self, instance, owner):
        # getattr just to avoid the protected member warning
        data: DataCarrier = getattr(instance, '_data')
        return data.updated_or_data(self._name)

    def __set__(self, instance, value):
        raise AttributeError(f"Attribute \"{self._name}\" is read only")


class Value(Generic[T]):
    def __init__(self, name: str):
        self._name = name

    def __get__(self, instance, owner):
        # getattr just to avoid the protected member warning
        data: DataCarrier = getattr(instance, '_data')
        return data.updated_or_data(self._name)

    def __set__(self, instance, value):
        # getattr just to avoid the protected member warning
        data: DataCarrier = getattr(instance, '_data')
        data.updated[self._name] = value


class Model(object):
    def __init__(self, api: 'RestApi', data):
        self._api = api
        self._data = DataCarrier(data)

    id: ReadOnlyValue[str] = ReadOnlyValue('id')

    def refresh(self):
        self._data = self._api.bots.fetch(self.id)._data


class Bot(Model):
    creator_id: ReadOnlyValue[str] = ReadOnlyValue('creator_id')
    host_id: Value[str] = Value('host_id')
    cluster_id: Value[str] = Value('cluster_id')
    current_job_id: ReadOnlyValue[str] = ReadOnlyValue('current_job_id')

    name: Value[str] = Value('name')
    type: ReadOnlyValue[str] = ReadOnlyValue('type')
    status: Value[str] = Value('status')
    error_text: Value[str] = Value('error_text')
    driver: Value[str] = Value('driver')  # TODO Maybe transform?
    job_available: ReadOnlyValue[bool] = ReadOnlyValue('job_available')

    # seen_at: ReadOnlyValue[str] = ReadOnlyValue('seen_at')  # TODO Date transform
    # created_at: ReadOnlyValue[str] = ReadOnlyValue('created_at')  # TODO Date transform
    # updated_at: ReadOnlyValue[str] = ReadOnlyValue('updated_at')  # TODO Date transform

    @property
    def current_job(self) -> Optional['Job']:
        if self.current_job_id is None:
            return None

        return self._api.jobs.fetch(self.current_job_id)

    @property
    def creator(self) -> 'User':
        return self._api.users.fetch(self.creator_id)


class Job(Model):
    creator_id: ReadOnlyValue[str] = ReadOnlyValue('creator_id')
    worker_id: ReadOnlyValue[str] = ReadOnlyValue('worker_id')
    worker_type: ReadOnlyValue[str] = ReadOnlyValue('worker_type')
    bot_id: ReadOnlyValue[Optional[str]] = ReadOnlyValue('bot_id')
    file_id: ReadOnlyValue[str] = ReadOnlyValue('file_id')

    name: Value[str] = Value('name')
    status: Value[str] = Value('status')
    progress: Value[str] = Value('progress')

    # created_at: ReadOnlyValue[str] = ReadOnlyValue('created_at')  # TODO Date transform
    # updated_at: ReadOnlyValue[str] = ReadOnlyValue('updated_at')  # TODO Date transform

    @property
    def file(self) -> 'File':
        return self._api.files.fetch(self.file_id)

    @property
    def creator(self) -> 'User':
        return self._api.users.fetch(self.creator_id)


class File(Model):
    uploader_id: ReadOnlyValue[str] = ReadOnlyValue('uploader_id')

    name: Value[str] = Value('name')
    size: ReadOnlyValue[int] = ReadOnlyValue('size')
    type: ReadOnlyValue[str] = ReadOnlyValue('type')

    # created_at: ReadOnlyValue[str] = ReadOnlyValue('created_at')  # TODO Date transform
    # updated_at: ReadOnlyValue[str] = ReadOnlyValue('updated_at')  # TODO Date transform

    @property
    def creator(self) -> 'User':
        return self._api.users.fetch(self.uploader_id)


class User(Model):
    username: ReadOnlyValue['str'] = ReadOnlyValue('username')

    # created_at: ReadOnlyValue[str] = ReadOnlyValue('created_at')  # TODO Date transform
    # updated_at: ReadOnlyValue[str] = ReadOnlyValue('updated_at')  # TODO Date transform
