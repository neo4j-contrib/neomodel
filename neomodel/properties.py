import functools
import json
import re
import sys
import uuid
from datetime import date, datetime

import neo4j.time
import pytz

from neomodel import config
from neomodel.exceptions import DeflateError, InflateError

TOO_MANY_DEFAULTS = "too many defaults"


def validator(fn):
    fn_name = fn.func_name if hasattr(fn, "func_name") else fn.__name__
    if fn_name == "inflate":
        exc_class = InflateError
    elif fn_name == "deflate":
        exc_class = DeflateError
    else:
        raise ValueError("Unknown Property method " + fn_name)

    @functools.wraps(fn)
    def _validator(self, value, obj=None, rethrow=True):
        if rethrow:
            try:
                return fn(self, value)
            except Exception as e:
                raise exc_class(self.name, self.owner, str(e), obj) from e
        else:
            # For using with ArrayProperty where we don't want an Inflate/Deflate error.
            return fn(self, value)

    return _validator


class FulltextIndex(object):
    """
    Fulltext index definition
    """

    def __init__(
        self,
        analyzer="standard-no-stop-words",
        eventually_consistent=False,
    ):
        """
        Initializes new fulltext index definition with analyzer and eventually consistent

        :param str analyzer: The analyzer to use. Defaults to "standard-no-stop-words".
        :param bool eventually_consistent: Whether the index should be eventually consistent. Defaults to False.
        """
        self.analyzer = analyzer
        self.eventually_consistent = eventually_consistent


class VectorIndex(object):
    """
    Vector index definition
    """

    def __init__(self, dimensions=1536, similarity_function="cosine"):
        """
        Initializes new vector index definition with dimensions and similarity

        :param int dimensions: The number of dimensions of the vector. Defaults to 1536.
        :param str similarity_function: The similarity algorithm to use. Defaults to "cosine".
        """
        self.dimensions = dimensions
        self.similarity_function = similarity_function


class Property:
    """
    Base class for object properties.

    :param unique_index: Creates a unique index for this property. Defaults to
                         ``False``.
    :type unique_index: :class:`bool`
    :param index: Creates an index for this property. Defaults to ``False``.
    :type index: :class:`bool`
    :param fulltext_index: Creates a fulltext index for this property. Defaults to ``None``.
    :type fulltext_index: :class:`FulltextIndex`
    :param vector_index: Creates a vector index for this property. Defaults to ``None``.
    :type vector_index: :class:`VectorIndex`
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

    form_field_class = "CharField"

    # pylint:disable=unused-argument
    def __init__(
        self,
        unique_index=False,
        index=False,
        fulltext_index: FulltextIndex = None,
        vector_index: VectorIndex = None,
        required=False,
        default=None,
        db_property=None,
        label=None,
        help_text=None,
        **kwargs,
    ):
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
        self.fulltext_index = fulltext_index
        self.vector_index = vector_index
        self.default = default
        self.has_default = self.default is not None
        self.db_property = db_property
        self.label = label
        self.help_text = help_text

    def default_value(self):
        """
        Generate a default value

        :return: the value
        """
        if self.has_default:
            if hasattr(self.default, "__call__"):
                return self.default()
            return self.default
        raise ValueError("No default value specified")

    def get_db_property_name(self, attribute_name):
        """
        Returns the name that should be used for the property in the database. This is db_property if supplied upon
        construction, otherwise the given attribute_name from the model is used.
        """
        return self.db_property or attribute_name

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
        default = super().default_value()
        return self.normalize(default)

    def normalize(self, value):
        raise NotImplementedError("Specialize normalize method")


class RegexProperty(NormalizedProperty):
    r"""
    Validates a property against a regular expression.

    If sub-classing set:

        expression = r'[^@]+@[^@]+\.[^@]+'
    """

    form_field_class = "RegexField"

    expression = None

    def __init__(self, expression=None, **kwargs):
        """
        Initializes new property with an expression.

        :param str expression: regular expression validating this property
        """
        super().__init__(**kwargs)
        actual_re = expression or self.expression
        if actual_re is None:
            raise ValueError("expression is undefined")
        self.expression = actual_re

    def normalize(self, value):
        normal = str(value)
        if not re.match(self.expression, normal):
            raise ValueError(f"{value!r} does not match {self.expression!r}")
        return normal


class EmailProperty(RegexProperty):
    """
    Store email addresses
    """

    form_field_class = "EmailField"
    expression = r"[^@]+@[^@]+\.[^@]+"


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
                raise ValueError(
                    "The arguments `choices` and `max_length` are mutually exclusive."
                )
            if max_length < 1:
                raise ValueError("`max_length` cannot be zero or take negative values.")

        super().__init__(**kwargs)

        self.max_length = max_length
        if choices is None:
            self.choices = None
        else:
            try:
                self.choices = dict(choices)
            except Exception as exc:
                raise ValueError(
                    "The choices argument must be convertible to a dictionary."
                ) from exc
            self.form_field_class = "TypedChoiceField"

    def normalize(self, value):
        # One thing to note here is that the following two checks can remain uncoupled
        # as long as it is guaranteed (by the constructor) that `choices` and `max_length`
        # are mutually exclusive. If that check in the constructor ever has to be removed,
        # these two validation checks here will have to be coupled so that having set
        # `choices` overrides having set the `max_length`.
        if self.choices is not None and value not in self.choices:
            raise ValueError(f"Invalid choice: {value}")
        if self.max_length is not None and len(value) > self.max_length:
            raise ValueError(
                f"Property max length exceeded. Expected {self.max_length}, got {len(value)} == len('{value}')"
            )
        return str(value)

    def default_value(self):
        return self.normalize(super().default_value())


class IntegerProperty(Property):
    """
    Stores an Integer value
    """

    form_field_class = "IntegerField"

    @validator
    def inflate(self, value):
        return int(value)

    @validator
    def deflate(self, value):
        return int(value)

    def default_value(self):
        return int(super().default_value())


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
                raise TypeError("Expecting neomodel Property")

            if isinstance(base_property, ArrayProperty):
                raise TypeError("Cannot have nested ArrayProperty")

            for illegal_attr in [
                "default",
                "index",
                "unique_index",
                "required",
            ]:
                if getattr(base_property, illegal_attr, None):
                    raise ValueError(
                        f'ArrayProperty base_property cannot have "{illegal_attr}" set'
                    )

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


class FloatProperty(Property):
    """
    Store a floating point value
    """

    form_field_class = "FloatField"

    @validator
    def inflate(self, value):
        return float(value)

    @validator
    def deflate(self, value):
        return float(value)

    def default_value(self):
        return float(super().default_value())


class BooleanProperty(Property):
    """
    Stores a boolean value
    """

    form_field_class = "BooleanField"

    @validator
    def inflate(self, value):
        return bool(value)

    @validator
    def deflate(self, value):
        return bool(value)

    def default_value(self):
        return bool(super().default_value())


class DateProperty(Property):
    """
    Stores a date
    """

    form_field_class = "DateField"

    @validator
    def inflate(self, value):
        if isinstance(value, neo4j.time.DateTime):
            value = date(value.year, value.month, value.day)
        elif isinstance(value, str) and "T" in value:
            value = value[: value.find("T")]
        return datetime.strptime(str(value), "%Y-%m-%d").date()

    @validator
    def deflate(self, value):
        if not isinstance(value, date):
            msg = f"datetime.date object expected, got {repr(value)}"
            raise ValueError(msg)
        return value.isoformat()


class DateTimeFormatProperty(Property):
    """
    Store a datetime by custom format
    :param default_now: If ``True``, the creation time (Local) will be used as default.
                        Defaults to ``False``.
    :param format:      Date format string, default is %Y-%m-%d

    :type default_now:  :class:`bool`
    :type format:       :class:`str`
    """

    form_field_class = "DateTimeFormatField"

    def __init__(self, default_now=False, format="%Y-%m-%d", **kwargs):
        if default_now:
            if "default" in kwargs:
                raise ValueError(TOO_MANY_DEFAULTS)
            kwargs["default"] = datetime.now()

        self.format = format
        super().__init__(**kwargs)

    @validator
    def inflate(self, value):
        return datetime.strptime(str(value), self.format)

    @validator
    def deflate(self, value):
        if not isinstance(value, datetime):
            raise ValueError(f"datetime object expected, got {type(value)}.")
        return datetime.strftime(value, self.format)


class DateTimeProperty(Property):
    """A property representing a :class:`datetime.datetime` object as
    unix epoch.

    :param default_now: If ``True``, the creation time (UTC) will be used as default.
                        Defaults to ``False``.
    :type default_now: :class:`bool`
    """

    form_field_class = "DateTimeField"

    def __init__(self, default_now=False, **kwargs):
        if default_now:
            if "default" in kwargs:
                raise ValueError(TOO_MANY_DEFAULTS)
            kwargs["default"] = lambda: datetime.utcnow().replace(tzinfo=pytz.utc)

        super().__init__(**kwargs)

    @validator
    def inflate(self, value):
        try:
            epoch = float(value)
        except ValueError as exc:
            raise ValueError(
                f"Float or integer expected, got {type(value)} cannot inflate to datetime."
            ) from exc
        except TypeError as exc:
            raise TypeError(
                f"Float or integer expected. Can't inflate {type(value)} to datetime."
            ) from exc
        return datetime.utcfromtimestamp(epoch).replace(tzinfo=pytz.utc)

    @validator
    def deflate(self, value):
        if not isinstance(value, datetime):
            raise ValueError(f"datetime object expected, got {type(value)}.")
        if value.tzinfo:
            value = value.astimezone(pytz.utc)
            epoch_date = datetime(1970, 1, 1, tzinfo=pytz.utc)
        elif config.FORCE_TIMEZONE:
            raise ValueError(f"Error deflating {value}: No timezone provided.")
        else:
            # No timezone specified on datetime object.. assuming UTC
            epoch_date = datetime(1970, 1, 1)
        return float((value - epoch_date).total_seconds())


class DateTimeNeo4jFormatProperty(Property):
    """
    Store a datetime by native neo4j format

    :param default_now: If ``True``, the creation time (Local) will be used as default.
                        Defaults to ``False``.

    :type default_now:  :class:`bool`
    """

    form_field_class = "DateTimeNeo4jFormatField"

    def __init__(self, default_now=False, **kwargs):
        if default_now:
            if "default" in kwargs:
                raise ValueError(TOO_MANY_DEFAULTS)
            kwargs["default"] = datetime.now()

        self.format = format
        super(DateTimeNeo4jFormatProperty, self).__init__(**kwargs)

    @validator
    def inflate(self, value):
        return value.to_native()

    @validator
    def deflate(self, value):
        if not isinstance(value, datetime):
            raise ValueError("datetime object expected, got {0}.".format(type(value)))
        return neo4j.time.DateTime.from_native(value)


class JSONProperty(Property):
    """
    Store a data structure as a JSON string.

    The structure will be inflated when a node is retrieved.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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
        for item in ["required", "unique_index", "index", "default"]:
            if item in kwargs:
                raise ValueError(
                    f"{item} argument ignored by {self.__class__.__name__}"
                )

        kwargs["unique_index"] = True
        kwargs["default"] = lambda: uuid.uuid4().hex
        super().__init__(**kwargs)

    @validator
    def inflate(self, value):
        return str(value)

    @validator
    def deflate(self, value):
        return str(value)
