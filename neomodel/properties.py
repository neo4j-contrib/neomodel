import functools
import json
import sys
import re
import uuid
import warnings
from abc import ABCMeta, abstractmethod
from datetime import date, datetime

import pytz

from neomodel import config
from neomodel.exceptions import InflateError, DeflateError


def validator(fn):
    fn_name = fn.func_name if hasattr(fn, 'func_name') else fn.__name__
    if fn_name == 'inflate':
        exc_class = InflateError
    elif fn_name == 'deflate':
        exc_class = DeflateError
    else:
        raise Exception("Unknown Property method " + fn_name)

    @functools.wraps(fn)
    def _validator(self, value, obj=None, rethrow=True):
        if rethrow:
            try:
                return fn(self, value)
            except Exception as e:
                raise exc_class(self.name, self.owner, str(e), obj)
        else:
            # For using with ArrayProperty where we don't want an Inflate/Deflate error.
            return fn(self, value)

    return _validator


# abstract property base classes


class Property(object):
    """
    Base class for object properties.

    :param unique_index: Creates a unique index for this property. Defaults to
                         ``False``.
    :type unique_index: :class:`bool`
    :param index: Creates an index for this property. Defaults to ``False``.
    :type index: :class:`bool`
    :param required: Marks the property as required. Defaults to ``False``.
    :type required: :class:`bool`
    :param default: A default value or callable that returns one to set when a
                    node is initialized without specifying this property.
    :param db_property: A name that this property maps to in the database.
                        Defaults to the model's property name.
    :type db_property: :class:`str`
    :param label: Optional, used by ``django_neomodel``.
    :type label: :class:`str`
    :param help_text: Optional, used by ``django_neomodel``.
    :type help_text: :class:`str`
    """

    form_field_class = 'CharField'

    def __init__(self, unique_index=False, index=False, required=False, default=None,
                 db_property=None, label=None, help_text=None, **kwargs):

        if default is not None and required:
            raise ValueError(
                "The arguments `required` and `default` are mutually exclusive."
            )
        if unique_index and index:
            raise ValueError(
                "The arguments `unique_index` and `index` are mutually exclusive."
            )

        self.required = required
        self.unique_index = unique_index
        self.index = index
        self.default = default
        self.has_default = True if self.default is not None else False
        self.db_property = db_property
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

    @abstractmethod
    @validator
    def deflate(self, value):
        pass

    @abstractmethod
    @validator
    def inflate(self, value):
        pass

    @property
    def is_indexed(self):
        return self.unique_index or self.index


Property = ABCMeta('Property', (Property,), {})


class NormalizedProperty(Property):
    """
    Base class for normalized properties. These use the same normalization
    method to in- or deflating.
    """

    @validator
    def inflate(self, value):
        return self.normalize(value)

    @validator
    def deflate(self, value):
        return self.normalize(value)

    def default_value(self):
        default = super().default_value()
        return self.normalize(default)

    @abstractmethod
    def normalize(self, value):
        pass


class _TypedProperty(NormalizedProperty):
    type = None

    def normalize(self, value):
        return self.type(value)

    def default_value(self):
        return self.type(super().default_value())


TypedProperty = ABCMeta('TypedProperty', (_TypedProperty,), {})


# property types


class RegexProperty(NormalizedProperty):
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
        super().__init__(**kwargs)
        actual_re = expression or self.expression
        if actual_re is None:
            raise ValueError('expression is undefined')
        self.expression = actual_re

    def normalize(self, value):
        if not re.match(self.expression, value):
            raise ValueError(
                "'{value}' doesn't match '{pattern}'."
                .format(value=value, pattern=self.expression)
            )
        return value


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


class ArrayProperty(Property):
    """
    Stores a list of items
    """

    def __init__(self, base_property=None, **kwargs):
        """
        Store a list of values, optionally of a specific type.

        :param base_property: List item type e.g StringProperty for string
        :type: Property
        """

        # list item type
        if base_property is not None:
            if not isinstance(base_property, Property):
                raise TypeError('Expecting neomodel Property')

            if isinstance(base_property, ArrayProperty):
                raise TypeError('Cannot have nested ArrayProperty')

            for ilegal_attr in ['default', 'index', 'unique_index', 'required']:
                if getattr(base_property, ilegal_attr, None):
                    raise ValueError('ArrayProperty base_property cannot have "{}" set'.format(ilegal_attr))

        self.base_property = base_property

        super().__init__(**kwargs)

    @validator
    def inflate(self, value):
        if self.base_property:
            return [self.base_property.inflate(item, rethrow=False) for item in value]

        return list(value)

    @validator
    def deflate(self, value):
        if self.base_property:
            return [self.base_property.deflate(item, rethrow=False) for item in value]

        return list(value)

    def default_value(self):
        return list(super().default_value())


class BooleanProperty(TypedProperty):
    """
    Stores a boolean value
    """
    form_field_class = 'BooleanField'
    type = bool


class DateProperty(Property):
    """
    Stores a date
    """
    form_field_class = 'DateField'

    @validator
    def inflate(self, value):
        return datetime.strptime(value, "%Y-%m-%d").date()

    @validator
    def deflate(self, value):
        if not isinstance(value, date):
            msg = 'datetime.date object expected, got {0}'.format(repr(value))
            raise ValueError(msg)
        return value.isoformat()


class DateTimeProperty(Property):
    """ A property representing a :class:`datetime.datetime` object as
        unix epoch.

        :param default_now: If ``True``, the creation time (UTC) will be used as default.
                            Defaults to ``False``.
        :type default_now: :class:`bool`
    """
    form_field_class = 'DateTimeField'

    def __init__(self, default_now=False, **kwargs):
        if default_now:
            if 'default' in kwargs:
                raise ValueError('too many defaults')
            kwargs['default'] = lambda: datetime.utcnow().replace(tzinfo=pytz.utc)

        super().__init__(**kwargs)

    @validator
    def inflate(self, value):
        try:
            epoch = float(value)
        except ValueError:
            raise ValueError("Float or integer expected, got {0} can't inflate to "
                             "datetime.".format(type(value)))
        return datetime.utcfromtimestamp(epoch).replace(tzinfo=pytz.utc)

    @validator
    def deflate(self, value):
        if not isinstance(value, datetime):
            raise ValueError('datetime object expected, got {0}.'.format(type(value)))
        if value.tzinfo:
            value = value.astimezone(pytz.utc)
            epoch_date = datetime(1970, 1, 1, tzinfo=pytz.utc)
        elif config.FORCE_TIMEZONE:
            raise ValueError("Error deflating {}: No timezone provided.".format(value))
        else:
            # No timezone specified on datetime object.. assuming UTC
            epoch_date = datetime(1970, 1, 1)
        return float((value - epoch_date).total_seconds())


class EmailProperty(RegexProperty):
    """
    Store email addresses
    """
    form_field_class = 'EmailField'
    expression = r'[^@]+@[^@]+\.[^@]+'


class FloatProperty(TypedProperty):
    """
    Store a floating point value
    """
    form_field_class = 'FloatField'
    type = float


class IntegerProperty(TypedProperty):
    """
    Stores an Integer value
    """
    form_field_class = 'IntegerField'
    type = int


class JSONProperty(Property):
    """
    Store a data structure as a JSON string.

    The structure will be inflated when a node is retrieved.
    """
    @validator
    def inflate(self, value):
        return json.loads(value)

    @validator
    def deflate(self, value):
        return json.dumps(value)


class StringProperty(_TypedProperty):
    """
    Stores a unicode string

    :param choices: A mapping of valid strings to label strings that are used
                    to display information in an application. If the default
                    value ``None`` is used, any string is valid.
    :type choices: Any type that can be used to initiate a :class:`dict`.
    """
    form_field_class = 'TypedChoiceField'
    type = str

    def __init__(self, choices=None, **kwargs):
        super().__init__(**kwargs)

        if choices is None:
            self.choices = None
        else:
            try:
                self.choices = dict(choices)
            except Exception as e:
                raise ValueError("The choices argument must be convertable to "
                                 "a dictionary.") from e

    def normalize(self, value):
        value = super().normalize(value)
        if self.choices is not None and value not in self.choices:
            raise ValueError("Invalid choice: {}".format(value))
        return value

    def default_value(self):
        return self.normalize(super().default_value())


class UniqueIdProperty(TypedProperty):
    """
    A unique identifier, a randomly generated uid (uuid4) with a unique index
    """

    type = str

    def __init__(self, **kwargs):
        for item in ['required', 'unique_index', 'index', 'default']:
            if item in kwargs:
                raise ValueError('{} argument ignored by {}'.format(item, self.__class__.__name__))

        kwargs['unique_index'] = True
        kwargs['default'] = lambda: uuid.uuid4().hex
        super().__init__(**kwargs)


