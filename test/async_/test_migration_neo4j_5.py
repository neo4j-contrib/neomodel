from test._async_compat import mark_async_test

import pytest

from neomodel import (
    AsyncRelationshipTo,
    AsyncStructuredNode,
    AsyncStructuredRel,
    IntegerProperty,
    StringProperty,
    adb,
)


class Album(AsyncStructuredNode):
    name = StringProperty()


class Released(AsyncStructuredRel):
    year = IntegerProperty()


class Band(AsyncStructuredNode):
    name = StringProperty()
    released = AsyncRelationshipTo(Album, relation_type="RELEASED", model=Released)


@mark_async_test
async def test_read_elements_id():
    the_hives = await Band(name="The Hives").save()
    lex_hives = await Album(name="Lex Hives").save()
    released_rel = await the_hives.released.connect(lex_hives)

    # Validate element_id properties
    assert lex_hives.element_id == (await the_hives.released.single()).element_id
    assert released_rel._start_node_element_id == the_hives.element_id
    assert released_rel._end_node_element_id == lex_hives.element_id

    # Validate id properties
    # Behaviour is dependent on Neo4j version
    db_version = await adb.database_version
    if db_version.startswith("4"):
        # Nodes' ids
        assert lex_hives.id == int(lex_hives.element_id)
        assert lex_hives.id == (await the_hives.released.single()).id
        # Relationships' ids
        assert isinstance(released_rel.element_id, str)
        assert int(released_rel.element_id) == released_rel.id
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
