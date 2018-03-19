from collections import ChainMap

from neomodel.exceptions import RequiredProperty
from neomodel.util import get_members_of_type
from neomodel.types import AliasPropertyType, AttributedType, PropertyType


class PropertyManagerMeta(type):
    def __new__(mcs, name, bases, namespace):
        property_definitions = {}
        for property_name in [x for x, y in namespace.items()
                     if isinstance(y, PropertyType)
                     and not isinstance(y, AliasPropertyType)]:
            if property_name.startswith('__'):
                raise ValueError("Properties' names must not start with '__'.")
            property_definitions[property_name] = namespace.pop(property_name)

        cls = super().__new__(mcs, name, bases, namespace)

        cls.__property_definitions__ = cls.__property_definitions__.copy()

        # cache various groups of properties
        for name, definition in property_definitions.items():
            cls.__property_definitions__[name] = definition
        cls.__alias_definitions__ = get_members_of_type(cls, AliasPropertyType)
        cls.__required_properties__ = tuple(
            x for x, y in cls.__property_definitions__.items()
            if y.required or y.unique_index
        )
        # FIXME? is this needed?
        cls.__property_and_alias_definitions__ = ChainMap(
            cls.__property_definitions__,
            cls.__alias_definitions__
        )

        for name, definition in cls.__property_and_alias_definitions__.items():
            mcs._setup_property(cls, name, definition)

        return cls

    @staticmethod
    def _setup_property(cls, name, definition):
        definition.name, definition.owner = name, cls
        # TODO document this feature
        if hasattr(definition, 'setup') and callable(definition.setup):
            definition.setup()


class PropertyManager(AttributedType, metaclass=PropertyManagerMeta):
    """
    Common methods for handling properties on node and relationship objects.
    """

    __abstract_node__ = True
    __property_definitions__ = {}

    def __init__(self, **kwargs):
        self.__properties__ = {}

        for name, definition in self.__property_definitions__.items():
            value = kwargs.pop(name, None)
            if value is None and getattr(definition, 'has_default', False):
                setattr(self, name, definition.default_value())
            else:
                setattr(self, name, value)

        for name in (x for x in self.__alias_definitions__ if x in kwargs):
            setattr(self, name, kwargs.pop(name))

        # model properties that are not mapped to the database
        for name, value in kwargs.items():
            setattr(self, name, value)

    def __getattr__(self, name):
        if name in self.__property_definitions__:
            return self.__properties__[name]
        # elif name in self.__alias_definitions__:
        #     return self.__properties__[self.__alias_definitions__[name].target]
        elif name.startswith('get_') and name.endswith('_display'):
            setattr(self, name, self.__make_get_display_method(name[4:-8]))
            return getattr(self, name)

        raise AttributeError

    def __make_get_display_method(self, name):
        def get_display_method():
            choices = self.__property_definitions__[name].choices
            return choices[self.__properties__[name]]
        return get_display_method

    def __setattr__(self, name, value):
        if name in self.__property_definitions__:
            self.__properties__[name] = value
        # elif name in self.__alias_definitions__:
        #     self.__properties__[self.__alias_definitions__[name].target] = value
        else:
            super().__setattr__(name, value)

    @classmethod
    def deflate(cls, properties, obj=None, skip_empty=False):
        # deflate dict ready to be stored
        deflated = {}
        for name, definition in cls.__property_definitions__.items():
            db_property = definition.db_property or name
            if properties.get(name) is not None:
                deflated[db_property] = definition.deflate(properties[name], obj)
            elif definition.has_default:
                deflated[db_property] = definition.deflate(
                    definition.default_value(), obj
                )
            elif definition.required or definition.unique_index:
                raise RequiredProperty(name, cls)
            elif not skip_empty:
                deflated[db_property] = None
        return deflated
