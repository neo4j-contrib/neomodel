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

    # Validate element_id properties
    assert lex_hives.element_id == the_hives.released.single().element_id
    assert released_rel._start_node_element_id == the_hives.element_id
    assert released_rel._end_node_element_id == lex_hives.element_id

    # Validate id properties
    # Behaviour is dependent on Neo4j version
    if db.database_version.startswith("4"):
        # Nodes' ids
        assert lex_hives.id == int(lex_hives.element_id)
        assert lex_hives.id == the_hives.released.single().id
        # Relationships' ids
        assert isinstance(released_rel.element_id, int)
        assert released_rel.element_id == released_rel.id
        assert released_rel._start_node_id == int(the_hives.element_id)
        assert released_rel._end_node_id == int(lex_hives.element_id)
    else:
        # Nodes' ids
        expected_error_type = ValueError
        expected_error_message = "id is deprecated in Neo4j version 5, please migrate to element_id\. If you use the id in a Cypher query, replace id\(\) by elementId\(\)\."
        assert isinstance(lex_hives.element_id, str)
        with pytest.raises(
            expected_error_type,
            match=expected_error_message,
        ):
            lex_hives.id

        # Relationships' ids
        assert isinstance(released_rel.element_id, str)
        assert isinstance(released_rel._start_node_element_id, str)
        assert isinstance(released_rel._end_node_element_id, str)
        with pytest.raises(
            expected_error_type,
            match=expected_error_message,
        ):
            released_rel.id
        with pytest.raises(
            expected_error_type,
            match=expected_error_message,
        ):
            released_rel._start_node_id
        with pytest.raises(
            expected_error_type,
            match=expected_error_message,
        ):
            released_rel._end_node_id
