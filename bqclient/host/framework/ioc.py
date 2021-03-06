import inspect


class FailureToBindException(Exception):
    pass


def singleton(cls):
    Resolver._singleton_annotation(cls)

    return cls


class Resolver(object):
    _resolver_instance = None
    _annotated_singletons = []

    def __init__(self):
        self._bindings = {}

        self.instance(self)

    def __call__(self, cls, *args, **kwargs):
        # Implicit binding
        if cls not in self._bindings:
            if cls in self._annotated_singletons:
                self.singleton(cls)
            else:
                self.bind(cls)

        return self._bindings[cls](*args, **kwargs)

    def _make(self, cls, *args, **kwargs):
        args_spec = inspect.getfullargspec(cls.__init__)

        args_dictionary = {}
        for arg in args:
            if hasattr(arg, '__class__'):
                args_dictionary[arg.__class__] = arg

        if len(args_spec.args) > 1:
            var_args = []

            for arg_spec in args_spec.args[1:]:
                if arg_spec in kwargs:
                    var_args.append(kwargs[arg_spec])
                elif arg_spec in args_spec.annotations:
                    argument_class = args_spec.annotations[arg_spec]

                    if argument_class in args_dictionary:
                        var_args.append(args_dictionary[argument_class])
                    else:
                        var_args.append(self.__call__(argument_class, *args))
                else:
                    message = f"Cannot bind argument {arg_spec} for class {cls}"
                    raise FailureToBindException(message)

            return cls(*var_args)

        return cls()

    def instance(self, cls, instance=None):
        if instance is None:
            if hasattr(cls, '__class__'):
                instance = cls
                cls = instance.__class__

        # Pretend we take arguments even though we always return the same instance
        def _internal(*_, **__):
            return instance

        self._bindings[cls] = _internal

    def bind(self, cls, bind_function=None):
        if bind_function is not None:
            _internal = bind_function
        else:
            def _internal(*args, **kwargs):
                return self._make(cls, *args, **kwargs)

        self._bindings[cls] = _internal

    @classmethod
    def _singleton_annotation(cls, singleton_cls):
        cls._annotated_singletons.append(singleton_cls)

    def singleton(self, cls, resolving_function=None):
        def _internal():
            # instance is set on the _internal function as opposed to a class level dictionary
            # so that if we ever re-bind or clear the binding of a singleton class, the existing
            # instance is automatically cleared

            if not hasattr(_internal, 'instance'):
                if resolving_function is None:
                    _internal.instance = self._make(cls)
                else:
                    _internal.instance = resolving_function()

            return _internal.instance

        self._bindings[cls] = _internal

    def clear(self, cls=None):
        if cls is None:
            for key in list(self._bindings.keys()):
                del self._bindings[key]

        elif cls in self._bindings:
            del self._bindings[cls]

    @classmethod
    def get(cls):
        if cls._resolver_instance is None:
            cls._resolver_instance = Resolver()

        return cls._resolver_instance

    @classmethod
    def reset(cls):
        cls._resolver_instance = None
