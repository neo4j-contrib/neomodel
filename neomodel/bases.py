import types
from collections import ChainMap

from neomodel.exceptions import RequiredProperty
from neomodel.util import (
    display_for, get_members_of_type, is_abstract_node_model
)
from neomodel.types import (
    AliasPropertyType, AttributedType, PropertyType, RelationshipManagerType
)


class PropertyManagerMeta(type):
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        if not is_abstract_node_model(cls):
            for property_name, property_instance in \
                    ((x, y) for x, y in namespace.items()
                     if isinstance(y, PropertyType)):
                mcs._setup_property(mcs, cls, property_name, property_instance)

            # cache various groups of properties
            cls.__property_definitions__ = \
                get_members_of_type(cls, PropertyType, AliasPropertyType)
            cls.__required_properties__ = tuple(
                x for x, y in cls.__property_definitions__.items()
                if y.required or y.unique_index
            )
            cls.__alias_definitions__ = \
                get_members_of_type(cls, AliasPropertyType)
            cls.__property_and_alias_definitions__ = ChainMap(
                cls.__property_definitions__,
                cls.__alias_definitions__
            )
            if any(x.startswith('__') for x
                   in cls.__property_and_alias_definitions__):
                raise ValueError("Properties' and aliases' names "
                                 "must not start with '__'.")

        return cls

    def _setup_property(mcs, cls, name, instance):
        instance.name, instance.owner = name, cls
        # TODO document this feature
        if hasattr(instance, 'setup') and callable(instance.setup):
            instance.setup()


class PropertyManager(AttributedType, metaclass=PropertyManagerMeta):
    """
    Common methods for handling properties on node and relationship objects.
    """

    __abstract_node__ = True

    def __init__(self, **kwargs):
        for name, definition in self.__property_definitions__.items():
            value = kwargs.pop(name, None)
            if value is None and getattr(definition, 'has_default', False):
                setattr(self, name, definition.default_value())
            else:
                setattr(self, name, value)

            # TODO set on-demand via __getattr__
            if getattr(definition, 'choices', None):
                setattr(self, 'get_{}_display'.format(name),
                        types.MethodType(display_for(name), self))

        for name in (x for x in self.__alias_definitions__ if x in kwargs):
            setattr(self, name, kwargs.pop(name))

        # model properties that are not mapped to the database
        for name, value in kwargs.items():
            setattr(self, name, value)

    @property
    def __properties__(self):  # TODO isn't this the same as __all_properties__ ?
        return {name: value for name, value in vars(self).items()
                if not name.startswith('_')
                and not callable(value)
                and not isinstance(value,
                                   (AliasPropertyType, RelationshipManagerType)
                                   )
                }

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
