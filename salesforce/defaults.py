import datetime
import decimal
from pytz import utc
from typing import Any, Dict, List, Optional, Tuple, Type

# from django.utils.deconstruct import deconstructible


# --- DefaultedOnCreate ---

# A multiple inheritance is problematic with the current mypy 0.770 and django-stubs v1.5.0
# probably related to  https://github.com/python/mypy/issues/3603
# Therefore many short methods are currently repeated instead of use Mixins.


class BaseDefault:

    default = None  # type: Any

    def __init__(self, *args):
        self.args = args

    def __str__(self) -> str:
        return StrDefault(super().__str__())

    def deconstruct(self) -> Tuple[str, List[Any], Dict]:
        if self == self.default:
            return ('salesforce.fields.DefaultedOnCreate', [], {})
        else:
            return ('salesforce.fields.DefaultedOnCreate', self.args, {})


class BoolDefault(BaseDefault, int):
    default = False
    # the type "int" is compatible with "bool" and the type "int" can be subclassed
    # e.g. assert 1 in {True}

    def __str__(self) -> str:
        return StrDefault(str(bool(self)))

    def __repr__(self) -> str:
        return 'salesforce.fields.DefaultedOnCreate({})'.format(bool(self))


class IntDefault(BaseDefault, int):
    default = 0


class FloatDefault(BaseDefault, float):
    default = 0.


class DecimalDefault(BaseDefault, decimal.Decimal):
    default = decimal.Decimal('0')


class StrDefault(BaseDefault, str):
    default = ''  # 'DEFAULTED_ON_CREATE'

    def __str__(self) -> str:
        return self


class DateDefault(BaseDefault, datetime.date):
    default = datetime.date(1700, 1, 1)

    def __new__(cls, *args, **kwargs):
        if len(args) == 1 and not kwargs:
            args = args[0].timetuple()[:3]
        return super().__new__(cls, *args, **kwargs)

    def isoformat(self) -> str:
        return StrDefault(super().isoformat())


class DateTimeDefault(BaseDefault, datetime.datetime):
    default = datetime.datetime(1700, 1, 1, 12, 0, 0, tzinfo=utc)

    def __new__(cls, *args, **kwargs):
        if len(args) == 1 and not kwargs:
            arg = args[0]
            args = arg.timetuple()[:6] + (arg.microsecond,)
            kwargs = {'tzinfo': arg.tzinfo}
        return super().__new__(cls, *args, **kwargs)

    def isoformat(self, sep: str = 'T', timecspec: str = 'auto') -> str:
        return StrDefault(super().isoformat())


class TimeDefault(BaseDefault, datetime.time):
    default = datetime.time(0, 0, 0)

    def __new__(cls, *args, **kwargs):
        if len(args) == 1 and not kwargs:
            arg = args[0]
            args = (arg.hour, arg.minute, arg.second, arg.microsecond)
            kwargs = {'tzinfo': arg.tzinfo}
        return super().__new__(cls, *args, **kwargs)

    def isoformat(self, timecspec: str = 'auto') -> str:
        return StrDefault(super().isoformat())


class CallableDefault(BaseDefault):
    default = None

    def __call__(self) -> Any:
        assert len(self.args) == 1
        out = self.args[0]()
        return DefaultedOnCreate.value_type_map[type(out)](out)


class DefaultedOnCreate:
    """
    The default value which denotes that the value should be skipped and
    replaced on the SFDC server later.

    It should not be replaced by Django, because SF can do it better or
    even no real value is accepted, neither None.
    SFDC can set the correct value only if the field is omitted in the REST API.
    (No normal soulution exists e.g. for some builtin foreign keys with
    SF attributes 'defaultedOnCreate: true, nillable: false')

    Example: `Owner` field is assigned to the current user if the field User is omitted.

        Owner = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                default=models.DefaultedOnCreate(),
                db_column='OwnerId')
    """
    field_type_map = {
        'BooleanField': BoolDefault,
        'CharField': StrDefault,
        'DateField': DateDefault,
        'DateTimeField': DateTimeDefault,
        'DecimalField': DecimalDefault,
        'DurationField': TimeDefault,
        'FilePathField': StrDefault,
        'FloatField': FloatDefault,
        'IntegerField': IntDefault,
        'BigIntegerField': IntDefault,
        'IPAddressField': StrDefault,
        'GenericIPAddressField': StrDefault,
        'NullBooleanField': BoolDefault,
        'PositiveIntegerField': IntDefault,
        'PositiveSmallIntegerField': IntDefault,
        'SlugField': StrDefault,
        'SmallIntegerField': IntDefault,
        'TextField': StrDefault,
        'TimeField': TimeDefault,

        'ForeignKey': StrDefault,

        'BinaryField': StrDefault,
        'UUIDField': StrDefault,
        'AutoField': StrDefault,
        'BigAutoField': StrDefault,
        'SmallAutoField': StrDefault,
    }  # type: Dict[str, Type]

    value_type_map = {type(klass.default): klass for klass in field_type_map.values()}

    def __new__(cls, value: Any = None, internal_type: Optional[str] = None) -> Any:
        if internal_type:
            klass = cls.field_type_map[internal_type]
            return klass(klass.default)
        elif value is not None:
            if callable(value):
                return CallableDefault(value)
            klass2 = cls.value_type_map.get(type(value))
            if klass2:
                return klass2(value)
            else:
                raise ValueError("The type of object '{}' not found for DefaultedOnCreate".format(value))
        else:
            # only one instance without parameters make sense, that is in DEFAULTED_ON_CREATE
            return super(DefaultedOnCreate, cls).__new__(cls)

    def deconstruct(self) -> Tuple[str, List[Any], Dict]:
        return ('salesforce.fields.DefaultedOnCreate', [], {})


DEFAULTED_ON_CREATE = DefaultedOnCreate()
