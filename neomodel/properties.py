from .exception import InflateError, DeflateError, RequiredProperty
from . import config

from datetime import datetime, date
from uuid import uuid4
import re
import types
import pytz
import json
import sys
import functools


if sys.version_info >= (3, 0):
    unicode = lambda x: str(x)


def display_for(key):
    def display_choice(self):
        return getattr(self.__class__, key).choice_map[getattr(self, key)]
    return display_choice


class PropertyManager(object):
    # Common methods for handling properties on node and relationship objects

    def __init__(self, *args, **kwargs):

        properties = getattr(self, "__all_properties__", None)
        if properties is None:
            properties = self.defined_properties(rels=False, aliases=False).items()
        for key, val in properties:
            # handle default values
            if key not in kwargs or kwargs[key] is None:
                if hasattr(val, 'has_default') and val.has_default:
                    setattr(self, key, val.default_value())
                else:
                    setattr(self, key, None)
            else:
                setattr(self, key, kwargs[key])

            if hasattr(val, 'choices') and getattr(val, 'choices'):
                setattr(self, 'get_{}_display'.format(key),
                        types.MethodType(display_for(key), self))

            if key in kwargs:
                del kwargs[key]

        aliases = getattr(self, "__all_aliases__", None)
        if aliases is None:
            aliases = self.defined_properties(rels=False, properties=False).items()
        # aliases next so they don't have their alias over written
        for key, val in aliases:
            if key in kwargs:
                setattr(self, key, kwargs[key])
                del kwargs[key]

        # undefined properties last (for magic @prop.setters etc)
        for key, val in kwargs.items():
            setattr(self, key, val)

    @property
    def __properties__(self):
        from .relationship_manager import RelationshipManager
        props = {}
        for key, value in self.__dict__.items():
            if not (key.startswith('_')
                    or isinstance(value,
                        (types.MethodType, RelationshipManager, AliasProperty,))):
                props[key] = value
        return props

    @classmethod
    def deflate(cls, obj_props, obj=None, skip_empty=False):
        # deflate dict ready to be stored
        deflated = {}
        for key, prop in cls.defined_properties(aliases=False, rels=False).items():
            # map property name to correct database property
            db_property = prop.db_property or key
            if key in obj_props and obj_props[key] is not None:
                deflated[db_property] = prop.deflate(obj_props[key], obj)
            elif prop.has_default:
                deflated[db_property] = prop.deflate(prop.default_value(), obj)
            elif prop.required or prop.unique_index:
                raise RequiredProperty(key, cls)
            elif skip_empty is not True:
                deflated[db_property] = None
        return deflated

    @classmethod
    def defined_properties(cls, aliases=True, properties=True, rels=True):
        from .relationship_manager import RelationshipDefinition
        props = {}
        for scls in reversed(cls.mro()):
            for key, prop in scls.__dict__.items():
                if ((aliases and isinstance(prop, AliasProperty))
                        or (properties and hasattr(prop, '__class__') and issubclass(prop.__class__, Property)
                            and not isinstance(prop, AliasProperty))
                        or (rels and isinstance(prop, RelationshipDefinition))):
                    props[key] = prop
        return props


def validator(fn):
    fn_name = fn.func_name if hasattr(fn, 'func_name') else fn.__name__
    if fn_name == 'inflate':
        exc_class = InflateError
    elif fn_name == 'deflate':
        exc_class = DeflateError
    else:
        raise Exception("Unknown Property method " + fn_name)

    @functools.wraps(fn)
    def validator(self, value, obj=None):
        try:
            return fn(self, value)
        except Exception as e:
            raise exc_class(self.name, self.owner, str(e), obj)
    return validator


class Property(object):
    """
    Base class for object properties
    """
    form_field_class = 'CharField'

    def __init__(self, unique_index=False, index=False, required=False, default=None,
                 db_property=None, label=None, help_text=None, **kwargs):
        """
        Define a new property

        :param unique_index: create unique index for this property
        :type: bool
        :param index: False
        :type: bool
        :param required: False
        :type: bool
        :param default: function or value
        :param db_property: name of neo4j property it should map to
        :type: str
        :param label: Optional, used by Django
        :type: str
        :param help_text: Optional, used by Django
        :type: str
        :param kwargs:
        """
        if default is not None and required:
            raise ValueError("required and default arguments are mutually exclusive")

        if unique_index and index:
            raise ValueError("unique_index and index arguments are mutually exclusive")

        self.required = required
        self.unique_index = unique_index
        self.index = index
        self.default = default
        self.has_default = True if self.default is not None else False
        self.db_property = db_property  # define the name of the property in the database
        self.label = label
        self.help_text = help_text

    def default_value(self):
        """
        Generate a default value

        :return: the value
        """
        if self.has_default:
            if hasattr(self.default, '__call__'):
                return self.default()
            else:
                return self.default
        else:
            raise Exception("No default value specified")

    @property
    def is_indexed(self):
        return self.unique_index or self.index


class NormalProperty(Property):
    """
    Base class for Normalized properties

    Those that use the same normalization method to inflate or deflate.
    """

    @validator
    def inflate(self, value):
        return self.normalize(value)

    @validator
    def deflate(self, value):
        return self.normalize(value)

    def default_value(self):
        default = super(NormalProperty, self).default_value()
        return self.normalize(default)

    def normalize(self, value):
        raise NotImplementedError('Specialize normalize method')


class RegexProperty(NormalProperty):
    """
    Validates a property against a regular expression.

    If sub-classing set:

        expression = r'[^@]+@[^@]+\.[^@]+'
    """
    form_field_class = 'RegexField'

    expression = None

    def __init__(self, expression=None, **kwargs):
        """
        Initializes new property with an expression.

        :param str expression: regular expression validating this property
        """
        super(RegexProperty, self).__init__(**kwargs)
        actual_re = expression or self.expression
        if actual_re is None:
            raise ValueError('expression is undefined')
        self.expression = actual_re

    def normalize(self, value):
        normal = unicode(value)
        if not re.match(self.expression, normal):
            raise ValueError(
                '{0!r} does not matches {1!r}'.format(
                    value,
                    self.expression,
                )
            )
        return normal


class EmailProperty(RegexProperty):
    """
    Store email addresses
    """
    form_field_class = 'EmailField'
    expression = r'[^@]+@[^@]+\.[^@]+'


class StringProperty(Property):
    """
    Store strings
    """
    def __init__(self, choices=None, **kwargs):
        """
        :param choices: tuple of tuple pairs.
        :type: tuple
        :param kwargs:
        """
        super(StringProperty, self).__init__(**kwargs)
        self.choices = choices

        if self.choices:
            if not isinstance(self.choices, tuple):
                raise ValueError("Choices must be a tuple of tuples")

            self.choice_map = dict(self.choices)
            self.form_field_class = 'TypedChoiceField'

    @validator
    def inflate(self, value):
        if self.choices and value not in self.choice_map:
            raise ValueError("Invalid choice {}".format(value))

        return unicode(value)

    @validator
    def deflate(self, value):
        if self.choices and value not in self.choice_map:
            raise ValueError("Invalid choice {}".format(value))

        return unicode(value)

    def default_value(self):
        return unicode(super(StringProperty, self).default_value())


class IntegerProperty(Property):
    """
    Stores an Integer value
    """
    form_field_class = 'IntegerField'

    @validator
    def inflate(self, value):
        return int(value)

    @validator
    def deflate(self, value):
        return int(value)

    def default_value(self):
        return int(super(IntegerProperty, self).default_value())


class ArrayProperty(Property):
    """
    Stores a list of items
    """
    @validator
    def inflate(self, value):
        return list(value)

    @validator
    def deflate(self, value):
        return list(value)

    def default_value(self):
        return list(super(ArrayProperty, self).default_value())


class FloatProperty(Property):
    """
    Store a floating point value
    """
    form_field_class = 'FloatField'

    @validator
    def inflate(self, value):
        return float(value)

    @validator
    def deflate(self, value):
        return float(value)

    def default_value(self):
        return float(super(FloatProperty, self).default_value())


class BooleanProperty(Property):
    """
    Stores a boolean value
    """
    form_field_class = 'BooleanField'

    @validator
    def inflate(self, value):
        return bool(value)

    @validator
    def deflate(self, value):
        return bool(value)

    def default_value(self):
        return bool(super(BooleanProperty, self).default_value())


class DateProperty(Property):
    """
    Stores a date
    """
    form_field_class = 'DateField'

    @validator
    def inflate(self, value):
        return datetime.strptime(unicode(value), "%Y-%m-%d").date()

    @validator
    def deflate(self, value):
        if not isinstance(value, date):
            msg = 'datetime.date object expected, got {0}'.format(repr(value))
            raise ValueError(msg)
        return value.isoformat()


class DateTimeProperty(Property):
    form_field_class = 'DateTimeField'

    def __init__(self, default_now=False, **kwargs):
        """
        Store a datetime.

        Serialises to unix epoch.

        :param bool default_now: default current date and time
        """
        if default_now:
            if 'default' in kwargs:
                raise ValueError('too many defaults')
            kwargs['default'] = lambda: datetime.utcnow().replace(tzinfo=pytz.utc)

        super(DateTimeProperty, self).__init__(**kwargs)

    @validator
    def inflate(self, value):
        try:
            epoch = float(value)
        except ValueError:
            raise ValueError('float or integer expected, got {0} cant inflate to datetime'.format(value))
        return datetime.utcfromtimestamp(epoch).replace(tzinfo=pytz.utc)

    @validator
    def deflate(self, value):
        if not isinstance(value, datetime):
            raise ValueError('datetime object expected, got {0}'.format(value))
        if value.tzinfo:
            value = value.astimezone(pytz.utc)
            epoch_date = datetime(1970, 1, 1, tzinfo=pytz.utc)
        elif config.FORCE_TIMEZONE:
            raise ValueError("Error deflating {} no timezone provided".format(value))
        else:
            # No timezone specified on datetime object.. assuming UTC
            epoch_date = datetime(1970, 1, 1)
        return float((value - epoch_date).total_seconds())


class JSONProperty(Property):
    """
    Store a data structure as a JSON string.

    The structure will be inflated when a node is retrieved.
    """
    def __init__(self, *args, **kwargs):
        super(JSONProperty, self).__init__(*args, **kwargs)

    @validator
    def inflate(self, value):
        return json.loads(value)

    @validator
    def deflate(self, value):
        return json.dumps(value)


class AliasProperty(property, Property):
    """
    Alias another existing property
    """
    def __init__(self, to=None):
        """
        Create new alias

        :param to: name of property aliasing
        :type: str
        """
        self.target = to
        self.required = False
        self.has_default = False

    def aliased_to(self):
        return self.target

    def __get__(self, obj, cls):
        return getattr(obj, self.aliased_to()) if obj else self

    def __set__(self, obj, value):
        setattr(obj, self.aliased_to(), value)

    @property
    def index(self):
        return getattr(self.owner, self.aliased_to()).index

    @property
    def unique_index(self):
        return getattr(self.owner, self.aliased_to()).unique_index


class UniqueIdProperty(Property):
    """
    A unique identifier, a randomly generated uid (uuid4) with a unique index
    """
    def __init__(self, **kwargs):
        for item in ['required', 'unique_index', 'index', 'default']:
            if item in kwargs:
                raise ValueError('{} argument ignored by {}'.format(item, self.__class__.__name__))

        kwargs['unique_index'] = True
        kwargs['default'] = lambda: uuid4().hex
        super(UniqueIdProperty, self).__init__(**kwargs)

    @validator
    def inflate(self, value):
        return unicode(value)

    @validator
    def deflate(self, value):
        return unicode(value)
