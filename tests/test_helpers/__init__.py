from threading import Event


class SideEffectEvent(object):
    def __init__(self):
        self._event = Event()

    def __call__(self, *args, **kwargs):
        self._event.set()

    def __bool__(self):
        return self._event.is_set()

    def wait(self, timeout=0.25):
        if timeout is None:
            raise ValueError("Timeout for side effect event cannot be None. The tests could block forever.")

        if timeout >= 5:
            # We don't want the overall test suite to take too long, so we limit the max value on this
            raise ValueError("Timeout for side effect event cannot be more than 5 seconds.")

        was_set = self._event.wait(timeout)

        if not was_set:
            raise Exception("Side effect event was never set")