"""
Unit tests for lazy optional-label resolution in the node-class registry.

A class's base label set is registered once; base+optional combinations are
resolved at lookup time rather than pre-materialised at registration (which is
exponential in the number of optional labels). DB-independent; it exercises the
shared registry logic via the sync instance.
"""

from neomodel import StringProperty, StructuredNode
from neomodel.sync_._registry import registry


class RegistryWidget(StructuredNode):
    __optional_labels__ = ["Shiny", "Heavy", "Fragile"]
    name = StringProperty()


BASE = frozenset(RegistryWidget.inherited_labels())  # {"RegistryWidget"}


def test_base_label_set_resolves():
    assert registry.get_class(BASE, None) is RegistryWidget


def test_optional_label_combinations_resolve():
    assert registry.get_class(BASE | {"Shiny"}, None) is RegistryWidget
    assert registry.get_class(BASE | {"Shiny", "Heavy"}, None) is RegistryWidget
    assert (
        registry.get_class(BASE | {"Shiny", "Heavy", "Fragile"}, None) is RegistryWidget
    )


def test_non_optional_extra_label_does_not_resolve():
    assert registry.get_class(BASE | {"NotDeclared"}, None) is None


def test_combinations_are_not_pre_materialised():
    # Only the base set is stored; the 2**3 optional combinations are not.
    assert BASE in registry._node_class_registry
    assert (BASE | {"Shiny"}) not in registry._node_class_registry
    assert (BASE | {"Shiny", "Heavy", "Fragile"}) not in registry._node_class_registry
