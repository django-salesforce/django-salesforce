# indep - optional functions and classes that should be independent on the
#         rest of salesforce to not make dependency graphs complicated
import uuid
from inspect import getcallargs
from typing import Any, Callable, Dict, Type

from django.conf import settings
from django.db.models import Field


class LazyField(object):
    """A Field that can be later customized until it is binded to the final Model"""
    # It does not need a deserializer for migrations because it is never passed
    # to migration tracking before before activation to a normal field

    counter = 0

    def __init__(self, klass: 'Type[Field[Any, Any]]') -> None:
        """Instantiate the field type"""
        self.klass = klass
        self.kw = {}  # type: Dict[str, Any]
        self.args = ()
        self.called = False
        self.counter = self.counter

    def __call__(self, *args: Any, **kwargs: Any) -> 'LazyField':
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

    def update(self, **kwargs: Any) -> 'LazyField':
        """Customize the lazy field"""
        assert not self.called
        self.kw.update(kwargs)
        return self

    def create(self) -> 'Field[Any, Any]':
        """Create a normal field from the lazy field"""
        assert not self.called
        return self.klass(*self.args, **self.kw)


def uuid_pk() -> str:
    return uuid.uuid4().hex


def get_sf_alt_pk() -> Callable[[], str]:
    return getattr(settings, 'SF_ALT_PK', uuid_pk)()  # type: ignore[no-any-return] # noqa
