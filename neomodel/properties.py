import functools
import json
import re
import uuid
from abc import ABCMeta, abstractmethod
from datetime import date, datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo

import neo4j.time

from neomodel.config import get_config
from neomodel.exceptions import DeflateError, InflateError, NeomodelException

TOO_MANY_DEFAULTS = "too many defaults"


def validator(fn: Callable) -> Callable:
    fn_name = fn.func_name if hasattr(fn, "func_name") else fn.__name__
    if fn_name not in ["inflate", "deflate"]:
        raise ValueError("Unknown Property method " + fn_name)

    @functools.wraps(fn)
    def _validator(  # type: ignore
        self, value: Any, obj: Any | None = None, rethrow: bool | None = True
    ) -> Any:
        if rethrow:
            try:
                return fn(self, value)
            except Exception as e:
                match fn_name:
                    case "inflate":
                        raise InflateError(self.name, self.owner, str(e), obj) from e
                    case "deflate":
                        raise DeflateError(self.name, self.owner, str(e), obj) from e
                    case _:
                        raise NeomodelException(
                            "Unknown Property method " + fn_name
                        ) from e
        else:
            # For using with ArrayProperty where we don't want an Inflate/Deflate error.
            return fn(self, value)

    return _validator


class FulltextIndex:
    """
    Fulltext index definition
    """

    def __init__(
        self,
        analyzer: str | None = "standard-no-stop-words",
        eventually_consistent: bool | None = False,
    ):
        """
        Initializes new fulltext index definition with analyzer and eventually consistent

        :param str analyzer: The analyzer to use. Defaults to "standard-no-stop-words".
        :param bool eventually_consistent: Whether the index should be eventually consistent. Defaults to False.
        """
        self.analyzer = analyzer
        self.eventually_consistent = eventually_consistent


class VectorIndex:
    """
    Vector index definition
    """

    def __init__(
        self,
        dimensions: int | None = 1536,
        similarity_function: str | None = "cosine",
    ):
        """
        Initializes new vector index definition with dimensions and similarity

        :param int dimensions: The number of dimensions of the vector. Defaults to 1536.
        :param str similarity_function: The similarity algorithm to use. Defaults to "cosine".
        """
        self.dimensions = dimensions
        self.similarity_function = similarity_function


class Property(metaclass=ABCMeta):
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
    name: str | None = None
    owner: Any | None = None
    unique_index: bool = False
    index: bool = False
    fulltext_index: FulltextIndex | None = None
    vector_index: VectorIndex | None = None
    required: bool = False
    default: Any = None
    db_property: str | None = None
    label: str | None = None
    help_text: str | None = None

    # pylint:disable=unused-argument
    def __init__(
        self,
        name: str | None = None,
        owner: Any | None = None,
        unique_index: bool = False,
        index: bool = False,
        fulltext_index: FulltextIndex | None = None,
        vector_index: VectorIndex | None = None,
        required: bool = False,
        default: Any | None = None,
        db_property: str | None = None,
        label: str | None = None,
        help_text: str | None = None,
        **kwargs: dict[str, Any],
    ):
        if default is not None and required:
            raise ValueError(
                "The arguments `required` and `default` are mutually exclusive."
            )
        if unique_index and index:
            raise ValueError(
                "The arguments `unique_index` and `index` are mutually exclusive."
            )

        self.name = name
        self.owner = owner
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
        # Set any extra kwargs as attributes on the property
        for key, value in kwargs.items():
            setattr(self, key, value)

    def default_value(self) -> Any:
        """
        Generate a default value

        :return: the value
        """
        if self.has_default:
            if hasattr(self.default, "__call__"):
                return self.default()
            return self.default
        raise ValueError("No default value specified")

    def get_db_property_name(self, attribute_name: str) -> str:
        """
        Returns the name that should be used for the property in the database. This is db_property if supplied upon
        construction, otherwise the given attribute_name from the model is used.
        """
        return self.db_property or attribute_name

    @property
    def is_indexed(self) -> bool:
        return self.unique_index or self.index

    @abstractmethod
    def inflate(self, value: Any, rethrow: bool = False) -> Any:
        pass

    @abstractmethod
    def deflate(self, value: Any, rethrow: bool = False) -> Any:
        pass


class NormalizedProperty(Property):
    """
    Base class for normalized properties. These use the same normalization
    method to in- or deflating.
    """

    @validator
    def inflate(self, value: Any) -> Any:
        return self.normalize(value)

    @validator
    def deflate(self, value: Any) -> Any:
        return self.normalize(value)

    def default_value(self) -> Any:
        default = super().default_value()
        return self.normalize(default)

    def normalize(self, value: Any) -> Any:
        raise NotImplementedError("Specialize normalize method")


class RegexProperty(NormalizedProperty):
    r"""
    Validates a property against a regular expression.

    If sub-classing set:

        expression = r'[^@]+@[^@]+\.[^@]+'
    """

    form_field_class = "RegexField"

    expression: str

    def __init__(self, expression: str | None = None, **kwargs: Any):
        """
        Initializes new property with an expression.

        :param str expression: regular expression validating this property
        """
        super().__init__(**kwargs)
        self.expression = expression or self.expression

    def normalize(self, value: Any) -> str:
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

    def __init__(
        self,
        choices: Any | None = None,
        max_length: int | None = None,
        **kwargs: Any,
    ):
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

    def normalize(self, value: str) -> str:
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

    def default_value(self) -> str:
        return self.normalize(super().default_value())


class IntegerProperty(Property):
    """
    Stores an Integer value
    """

    form_field_class = "IntegerField"

    @validator
    def inflate(self, value: Any) -> int:
        return int(value)

    @validator
    def deflate(self, value: Any) -> int:
        return int(value)

    def default_value(self) -> int:
        return int(super().default_value())


class ArrayProperty(Property):
    """
    Stores a list of items
    """

    def __init__(self, base_property: Property | None = None, **kwargs: Any):
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
    def inflate(self, value: Any) -> list:
        if self.base_property:
            return [self.base_property.inflate(item, rethrow=False) for item in value]

        return list(value)

    @validator
    def deflate(self, value: Any) -> list:
        if self.base_property:
            return [self.base_property.deflate(item, rethrow=False) for item in value]

        return list(value)

    def default_value(self) -> list:
        return list(super().default_value())


class FloatProperty(Property):
    """
    Store a floating point value
    """

    form_field_class = "FloatField"

    @validator
    def inflate(self, value: Any) -> float:
        return float(value)

    @validator
    def deflate(self, value: Any) -> float:
        return float(value)

    def default_value(self) -> float:
        return float(super().default_value())


class BooleanProperty(Property):
    """
    Stores a boolean value
    """

    form_field_class = "BooleanField"

    @validator
    def inflate(self, value: Any) -> bool:
        return bool(value)

    @validator
    def deflate(self, value: Any) -> bool:
        return bool(value)

    def default_value(self) -> bool:
        return bool(super().default_value())


class DateProperty(Property):
    """
    Stores a date
    """

    form_field_class = "DateField"

    @validator
    def inflate(self, value: Any) -> date:
        if isinstance(value, neo4j.time.DateTime):
            value = date(value.year, value.month, value.day)
        elif isinstance(value, str) and "T" in value:
            value = value[: value.find("T")]
        return datetime.strptime(str(value), "%Y-%m-%d").date()

    @validator
    def deflate(self, value: date) -> str:
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

    def __init__(
        self, default_now: bool = False, format: str = "%Y-%m-%d", **kwargs: Any
    ):
        if default_now:
            if "default" in kwargs:
                raise ValueError(TOO_MANY_DEFAULTS)
            kwargs["default"] = datetime.now()

        self.format = format
        super().__init__(**kwargs)

    @validator
    def inflate(self, value: Any) -> datetime:
        return datetime.strptime(str(value), self.format)

    @validator
    def deflate(self, value: datetime) -> str:
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

    def __init__(self, default_now: bool = False, **kwargs: Any):
        if default_now:
            if "default" in kwargs:
                raise ValueError(TOO_MANY_DEFAULTS)
            kwargs["default"] = lambda: datetime.now(ZoneInfo("UTC"))

        super().__init__(**kwargs)

    @validator
    def inflate(self, value: Any) -> datetime:
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
        return datetime.fromtimestamp(epoch, tz=ZoneInfo("UTC"))

    @validator
    def deflate(self, value: datetime) -> float:
        if not isinstance(value, datetime):
            raise ValueError(f"datetime object expected, got {type(value)}.")
        if value.tzinfo:
            value = value.astimezone(ZoneInfo("UTC"))
            epoch_date = datetime(1970, 1, 1, tzinfo=ZoneInfo("UTC"))
        elif get_config().force_timezone:
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

    def __init__(self, default_now: bool = False, **kwargs: Any):
        if default_now:
            if "default" in kwargs:
                raise ValueError(TOO_MANY_DEFAULTS)
            kwargs["default"] = datetime.now()

        self.format = format
        super(DateTimeNeo4jFormatProperty, self).__init__(**kwargs)

    @validator
    def inflate(self, value: Any) -> datetime:
        return value.to_native()

    @validator
    def deflate(self, value: datetime) -> neo4j.time.DateTime:
        if not isinstance(value, datetime):
            raise ValueError("datetime object expected, got {0}.".format(type(value)))
        return neo4j.time.DateTime.from_native(value)


class JSONProperty(Property):
    """
    Store a data structure as a JSON string.

    The structure will be inflated when a node is retrieved.
    """

    def __init__(self, ensure_ascii: bool = True, *args: Any, **kwargs: Any):
        self.ensure_ascii = ensure_ascii
        super(JSONProperty, self).__init__(*args, **kwargs)

    @validator
    def inflate(self, value: Any) -> Any:
        return json.loads(value)

    @validator
    def deflate(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=self.ensure_ascii)


class AliasProperty(property, Property):
    """
    Alias another existing property
    """

    def __init__(self, to: str):
        """
        Create new alias

        :param to: name of property aliasing
        :type: str
        """
        super().__init__()
        self.target = to
        self.required = False
        self.has_default = False

    def aliased_to(self) -> str:
        return self.target

    def __get__(self, obj: Any, _type: Any | None = None) -> Property:
        return getattr(obj, self.aliased_to()) if obj else self

    def __set__(self, obj: Any, value: Property) -> None:
        setattr(obj, self.aliased_to(), value)

    @property
    def index(self) -> bool:
        return getattr(self.owner, self.aliased_to()).index

    @index.setter
    def index(self, value: bool) -> None:
        raise AttributeError("Cannot set read-only property 'index'")

    @property
    def unique_index(self) -> bool:
        return getattr(self.owner, self.aliased_to()).unique_index

    @unique_index.setter
    def unique_index(self, value: bool) -> None:
        raise AttributeError("Cannot set read-only property 'unique_index'")


class UniqueIdProperty(Property):
    """
    A unique identifier, a randomly generated uid (uuid4) with a unique index
    """

    def __init__(self, **kwargs: Any):
        for item in ["required", "unique_index", "index", "default"]:
            if item in kwargs:
                raise ValueError(
                    f"{item} argument ignored by {self.__class__.__name__}"
                )

        kwargs["unique_index"] = True
        kwargs["default"] = lambda: uuid.uuid4().hex
        super().__init__(**kwargs)

    @validator
    def inflate(self, value: Any) -> str:
        return str(value)

    @validator
    def deflate(self, value: Any) -> str:
        return str(value)
