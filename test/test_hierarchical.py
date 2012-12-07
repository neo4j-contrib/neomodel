from neomodel.contrib import Hierarchical
from neomodel import StructuredNode, StringProperty


class CountryNode(Hierarchical, StructuredNode):
    code = StringProperty(unique_index=True)


class Nationality(Hierarchical, StructuredNode):
    code = StringProperty(unique_index=True)


def test_hierarchies():
    gb = CountryNode(code="GB").save()
    cy = CountryNode(code="CY").save()

    british = Nationality(__parent__=gb, code="GB-GB").save()
    greek_cypriot = Nationality(__parent__=cy, code="CY-GR").save()
    turkish_cypriot = Nationality(__parent__=cy, code="CY-TR").save()

    assert british.parent() == gb
    assert greek_cypriot.parent() == cy
    assert turkish_cypriot.parent() == cy
    assert greek_cypriot in cy.children(Nationality)
