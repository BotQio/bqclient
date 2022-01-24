from typing import Callable, Any, Generic, TypeVar, Optional

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
        self._cb: Optional[Callable[[T], Any]] = None

    def __get__(self, instance, owner) -> Callable[[T], Any]:
        def _inner(value: T):
            if self._cb is None:
                return
            try:
                self._cb(value)
            except BaseException:
                pass

        return _inner

    def __set__(self, instance, value: Callable[[T], Any]):
        self._cb = value


class Callback(object):
    def __init__(self):
        self._cb: Optional[Callable[[], Any]] = None

    def __get__(self, instance, owner) -> Callable[[], Any]:
        def _inner():
            if self._cb is None:
                return
            try:
                self._cb()
            except BaseException:
                pass

        return _inner

    def __set__(self, instance, value: Callable[[], Any]):
        self._cb = value
