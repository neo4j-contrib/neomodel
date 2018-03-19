"""
This module contains classes that are used as type definitions.
These can be used to identify the type of an object with :func:`isinstance`.
Hence classes that implement a type must base on one of these.
This provides more leverage with module's import dependencies.

As a rule of thumb any class that is used for tests with ``isinstance`` in
another module should be typed.
"""


class AttributedType:
    """ Type for models with properties. """


class NodeSetType:
    """ Type for a nodes containing sequence. """


class PropertyType:
    """ Type for property definitions. """


class RelationshipDefinitionType:
    """ Type for relationship definitions. """


#


class AliasPropertyType(PropertyType):
    """ Type for alias properties. """


class NodeType(AttributedType):
    """ Type for node models. """


class RelationshipType(AttributedType):
    """ Type for relationship models. """
