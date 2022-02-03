from typing import Callable, Any, Generic, TypeVar, Optional, Dict

T = TypeVar('T')

"""
These callbacks can have only one subscriber and swallow any exception that subscriber throws. They can be used like this:

class Foo(object):
    no_parameter_callback: Callback = Callback()
    parameter_callback: GenericCallback[str] = GenericCallback()
    
foo = Foo()
foo.no_parameter_callback = lambda: print("No Parameter needed!")
foo.parameter_callback = lambda data: print(f"I got some data: {data}")

foo.no_parameter_callback()
foo.parameter_callback("Hello World!")

The callbacks are safe to call even if there is no callback assigned to them.
"""


class GenericCallback(Generic[T]):
    def __init__(self):
        self._callbacks: Dict[int, Optional[Callable[[T], Any]]] = {}

    def __get__(self, instance, owner) -> Callable[[T], Any]:
        def _inner(value: T):
            cb = self._callbacks.setdefault(_inner.instance_id, None)

            if cb is None:
                return
            try:
                cb(value)
            except BaseException as ex:
                print(ex)

        _inner.instance_id = id(instance)

        return _inner

    def __set__(self, instance, value: Callable[[T], Any]):
        self._callbacks[id(instance)] = value


class Callback(object):
    def __init__(self):
        self._callbacks: Dict[int, Optional[Callable[[], Any]]] = {}

    def __get__(self, instance, owner) -> Callable[[], Any]:
        def _inner():
            cb = self._callbacks.setdefault(_inner.instance_id, None)

            if cb is None:
                return
            try:
                cb()
            except BaseException as ex:
                print(ex)

        _inner.instance_id = id(instance)

        return _inner

    def __set__(self, instance, value: Callable[[], Any]):
        self._callbacks[id(instance)] = value
