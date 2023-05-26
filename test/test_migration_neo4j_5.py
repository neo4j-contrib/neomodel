import pytest

from neomodel import (
    IntegerProperty,
    RelationshipTo,
    StringProperty,
    StructuredNode,
    StructuredRel,
)
from neomodel.core import db


class Album(StructuredNode):
    name = StringProperty()


class Released(StructuredRel):
    year = IntegerProperty()


class Band(StructuredNode):
    name = StringProperty()
    released = RelationshipTo(Album, relation_type="RELEASED", model=Released)


def test_read_elements_id():
    the_hives = Band(name="The Hives").save()
    lex_hives = Album(name="Lex Hives").save()
    released_rel = the_hives.released.connect(lex_hives)

    assert lex_hives.element_id == the_hives.released.single().element_id
    if db.database_version.startswith("4"):
        assert lex_hives.id == int(lex_hives.element_id)
        assert lex_hives.id == the_hives.released.single().id
        assert isinstance(released_rel.element_id, int)
        assert released_rel.element_id == released_rel.id
    else:
        assert isinstance(lex_hives.element_id, str)
        assert isinstance(released_rel.element_id, str)
        with pytest.raises(
            ValueError,
            match="id is deprecated in Neo4j version 5, please migrate to element_id\. If you use the id in a Cypher query, replace id\(\) by elementId\(\)\.",
        ):
            lex_hives.id
        with pytest.raises(
            ValueError,
            match="id is deprecated in Neo4j version 5, please migrate to element_id\. If you use the id in a Cypher query, replace id\(\) by elementId\(\)\.",
        ):
            released_rel.id
