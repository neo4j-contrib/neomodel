import types

from neomodel import config, db
from neomodel.exceptions import RequiredProperty
from neomodel.properties import AliasProperty, Property
from neomodel.util import display_for


class _RelationshipDefinition:
    # This class is solely intended to be used as base class for
    # relationship_manager.RelationshipDefinition in order to avoid
    # unresolvable import dependencies.
    pass


class PropertyManagerMeta(type):
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        if hasattr(cls, '__abstract_node__'):
            # TODO rather use a 'Meta' class à la Django?
            # or use an Abstract class that serves as marker
            # (also usable for property classes)
            delattr(cls, '__abstract_node__')
        else:
            if 'deleted' in namespace:
                raise ValueError("Class property called 'deleted' conflicts "
                                 "with neomodel internals.")
            for property_name, property_instance in \
                    ((x, y) for x, y in namespace.items()
                     if isinstance(y, Property)):
                mcs._setup_property(mcs, cls, property_name, property_instance)

            # cache various groups of properties
            # FIXME some of these should really be dicts
            cls.__required_properties__ = tuple(
                name for name, property
                in cls.defined_properties(aliases=False, rels=False).items()
                if property.required or property.unique_index
            )
            cls.__all_properties__ = tuple(
                cls.defined_properties(aliases=False, rels=False).items()
            )
            cls.__all_aliases__ = tuple(
                cls.defined_properties(properties=False, rels=False).items()
            )
            # FIXME node specific
            cls.__all_relationships__ = tuple(
                cls.defined_properties(aliases=False, properties=False).items()
            )

            cls.__label__ = namespace.get('__label__', name)

            if config.AUTO_INSTALL_LABELS:
                db.install_labels(cls)

        return cls

    def _setup_property(mcs, cls, name, instance):
        instance.name, instance.owner = name, cls
        # TODO document this feature
        if hasattr(instance, 'setup') and callable(instance.setup):
            instance.setup()


class PropertyManager(metaclass=PropertyManagerMeta):
    """
    Common methods for handling properties on node and relationship objects.
    """

    __abstract_node__ = True

    def __init__(self, **kwargs):
        properties = getattr(self, "__all_properties__", None)
        if properties is None:
            properties = \
                self.defined_properties(rels=False, aliases=False).items()
        # FIXME ^ so far this is very odd, __all_properties__ should be good to go
        for name, property in properties:
            if kwargs.get(name) is None:
                if getattr(property, 'has_default', False):
                    setattr(self, name, property.default_value())
                else:
                    setattr(self, name, None)
            else:
                setattr(self, name, kwargs[name])

            if getattr(property, 'choices', None):
                setattr(self, 'get_{}_display'.format(name),
                        types.MethodType(display_for(name), self))

            if name in kwargs:
                del kwargs[name]

        aliases = getattr(self, "__all_aliases__", None)
        if aliases is None:
            aliases = self.defined_properties(
                aliases=True, rels=False, properties=False).items()
        # FIXME ^ this is odd too
        for name, property in aliases:
            if name in kwargs:
                setattr(self, name, kwargs[name])
                del kwargs[name]

        # undefined properties (for magic @prop.setters etc)
        for name, property in kwargs.items():
            setattr(self, name, property)

    @property
    def __properties__(self):  # TODO isn't this the same as __all_properties__ ?
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
            elif property.required or property.unique_index:
                raise RequiredProperty(name, cls)
            elif not skip_empty:
                deflated[db_property] = None
        return deflated

    @classmethod
    def defined_properties(cls, aliases=True, properties=True, rels=True):
        props = {}
        for baseclass in reversed(cls.__mro__):
            props.update(dict(
                (name, property) for name, property in vars(baseclass).items()
                if (aliases and isinstance(property, AliasProperty))
                or (properties and isinstance(property, Property)
                    and not isinstance(property, AliasProperty))
                or (rels and isinstance(property, _RelationshipDefinition))
            ))
        return props

