import functools
import json
import sys
import types
import re
import uuid
import warnings
from datetime import date, datetime

import pytz

from neomodel import config
from neomodel.exceptions import InflateError, DeflateError, RequiredProperty


if sys.version_info >= (3, 0):
    unicode = str


def display_for(key):
    def display_choice(self):
        return getattr(self.__class__, key).choices[getattr(self, key)]
    return display_choice


class PropertyManager(object):
    """
    Common methods for handling properties on node and relationship objects.
    """

    def __init__(self, **kwargs):
        properties = getattr(self, "__all_properties__", None)
        if properties is None:
            properties = \
                self.defined_properties(rels=False, aliases=False).items()
        for name, property in properties:
            if kwargs.get(name) is None:
                if getattr(property, 'has_default', False):
                    setattr(self, name, property.default_value())
                else:
                    setattr(self, name, None)
            else:
                setattr(self, name, kwargs[name])

            if getattr(property, 'choices', None):
                setattr(self, 'get_{0}_display'.format(name),
                        types.MethodType(display_for(name), self))

            if name in kwargs:
                del kwargs[name]

        aliases = getattr(self, "__all_aliases__", None)
        if aliases is None:
            aliases = self.defined_properties(
                aliases=True, rels=False, properties=False).items()
        for name, property in aliases:
            if name in kwargs:
                setattr(self, name, kwargs[name])
                del kwargs[name]

        # undefined properties (for magic @prop.setters etc)
        for name, property in kwargs.items():
            setattr(self, name, property)

    @property
    def __properties__(self):
        from .relationship_manager import RelationshipManager

        return dict((name, value) for name, value in vars(self).items()
                    if not name.startswith('_')
                    and not callable(value)
                    and not isinstance(value,
                                       (RelationshipManager, AliasProperty,))
                    )

    @classmethod
    def deflate(cls, properties, obj=None, skip_empty=False):
        # deflate dict ready to be stored
        deflated = {}
        for name, property \
                in cls.defined_properties(aliases=False, rels=False).items():
            db_property = property.db_property or name
            if properties.get(name) is not None:
                deflated[db_property] = property.deflate(properties[name], obj)
            elif property.has_default:
                deflated[db_property] = property.deflate(
                    property.default_value(), obj
                )
            elif property.required:
                raise RequiredProperty(name, cls)
            elif not skip_empty:
                deflated[db_property] = None
        return deflated

    @classmethod
    def defined_properties(cls, aliases=True, properties=True, rels=True):
        from .relationship_manager import RelationshipDefinition
        props = {}
        for baseclass in reversed(cls.__mro__):
            props.update(dict(
                (name, property) for name, property in vars(baseclass).items()
                if (aliases and isinstance(property, AliasProperty))
                or (properties and isinstance(property, Property)
                    and not isinstance(property, AliasProperty))
                or (rels and isinstance(property, RelationshipDefinition))
            ))
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

    @property
    def is_indexed(self):
        return self.unique_index or self.index


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
        default = super(NormalizedProperty, self).default_value()
        return self.normalize(default)

    def normalize(self, value):
        raise NotImplementedError('Specialize normalize method')


# TODO remove this with the next major release
def _warn_NormalProperty_renamed():
    warnings.warn(
        'The class NormalProperty was renamed to NormalizedProperty. '
        'Use that one as base class. The former will be removed in the next '
        'major release.', DeprecationWarning)


if sys.version_info >= (3, 6):
    class NormalProperty(NormalizedProperty):

        def __init_subclass__(cls, **kwargs):
            _warn_NormalProperty_renamed()
else:
    class NormalProperty(NormalizedProperty):

        def __init__(self, *args, **kwargs):
            _warn_NormalProperty_renamed()
            super(NormalProperty, self).__init__(*args, **kwargs)
##


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


class StringProperty(NormalizedProperty):
    """
    Stores a unicode string

    :param choices: A mapping of valid strings to label strings that are used
                    to display information in an application. If the default
                    value ``None`` is used, any string is valid.
    :type choices: Any type that can be used to initiate a :class:`dict`.
    :param max_length: The maximum non-zero length that this attribute can be
    :type max_length: int
    """

    def __init__(self, choices=None, max_length=None, **kwargs):
        if max_length is not None:
            if choices is not None:
                raise ValueError("The arguments `choices` and `max_length` are mutually exclusive.")
            if max_length<1:
                raise ValueError("`max_length` cannot be zero or take negative values.")

        super(StringProperty, self).__init__(**kwargs)

        self.max_length = max_length
        if choices is None:
            self.choices = None
        else:
            try:
                self.choices = dict(choices)
            except Exception:
                raise ValueError("The choices argument must be convertable to a dictionary.")
            # Python 3:
            # except Exception as e:
            #     raise ValueError("The choices argument must be convertable to "
            #                      "a dictionary.") from e
            self.form_field_class = 'TypedChoiceField'

    def normalize(self, value):
        # One thing to note here is that the following two checks can remain uncoupled
        # as long as it is guaranteed (by the constructor) that `choices` and `max_length`
        # are mutually exclusive. If that check in the constructor ever has to be removed, 
        # these two validation checks here will have to be coupled so that having set 
        # `choices` overrides having set the `max_length`.
        if self.choices is not None and value not in self.choices:
            raise ValueError("Invalid choice: {}".format(value))
        if self.max_length is not None and len(value) > self.max_length:
            raise ValueError("Property max length exceeded. Expected {}, got {} == len('{}')".format(
                             self.max_length, len(value), value))
        return unicode(value)

    def default_value(self):
        return self.normalize(super(StringProperty, self).default_value())


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
                    raise ValueError('ArrayProperty base_property cannot have "{0}" set'.format(ilegal_attr))

        self.base_property = base_property

        super(ArrayProperty, self).__init__(**kwargs)

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

class DateTimeFormatProperty(Property):
    """
    Store a datetime by custome format
    :param default_now: If ``True``, the creation time (Local) will be used as default.
                        Defaults to ``False``.
    :param format:      Date format string, default is %Y-%m-%d

    :type default_now:  :class:`bool`
    :type format:       :class:`str`
    """
    form_field_class = 'DateTimeFormatField'

    def __init__(self, default_now=False, format="%Y-%m-%d", **kwargs):
        if default_now:
            if 'default' in kwargs:
                raise ValueError('too many defaults')
            kwargs['default'] = lambda: datetime.now()

        self.format = format
        super(DateTimeFormatProperty, self).__init__(**kwargs)

    @validator
    def inflate(self, value):
        return datetime.strptime(unicode(value), self.format)

    @validator
    def deflate(self, value):
        if not isinstance(value, datetime):
            raise ValueError('datetime object expected, got {0}.'.format(type(value)))
        return datetime.strftime(value, self.format)




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

        super(DateTimeProperty, self).__init__(**kwargs)

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
            raise ValueError("Error deflating {0}: No timezone provided.".format(value))
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
                raise ValueError('{0} argument ignored by {1}'.format(item, self.__class__.__name__))

        kwargs['unique_index'] = True
        kwargs['default'] = lambda: uuid.uuid4().hex
        super(UniqueIdProperty, self).__init__(**kwargs)

    @validator
    def inflate(self, value):
        return unicode(value)

    @validator
    def deflate(self, value):
        return unicode(value)
