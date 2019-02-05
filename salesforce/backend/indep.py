from inspect import getcallargs


class LazyField(object):
    """A Field that can be later customized until binded to the final Model"""
    # It does not need a deserializer for migrations because it is never passed
    # to migration tracking before before activation to a normal field

    counter = 0

    def __init__(self, klass):
        """Instantiate the field type"""
        self.klass = klass
        self.kw = {}
        self.args = ()
        self.called = False
        self.counter = self.counter

    def __call__(self, *args, **kwargs):
        """Instantiate a new field with options"""
        assert not self.called
        obj = type(self)(self.klass)
        # check valid args and check duplicite
        kw = getcallargs(self.klass.__init__, self, *args, **kwargs)  # pylint:disable=deprecated-method
        del kw['self']
        obj.args = kw.pop('args', ())
        kw.update(kw.pop('kwargs', {}))
        obj.kw = kw
        setattr(type(self), 'counter', getattr(type(self), 'counter') + 1)
        return obj

    def update(self, **kwargs):
        """Customize the lazy field"""
        assert not self.called
        self.kw.update(kwargs)
        return self

    def create(self):
        """Create a normal field from the lazy field"""
        assert not self.called
        return self.klass(*self.args, **self.kw)
