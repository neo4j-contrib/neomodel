from test._async_compat import mark_async_test

from neo4j.exceptions import ClientError

from neomodel import AsyncStructuredNode, StringProperty, adb


class ConstraintAndIndex(AsyncStructuredNode):
    name = StringProperty(unique_index=True)
    last_name = StringProperty(index=True)


@mark_async_test
async def test_drop_labels():
    await adb.install_labels(ConstraintAndIndex)
    constraints_before = await adb.list_constraints()
    indexes_before = await adb.list_indexes(exclude_token_lookup=True)

    assert len(constraints_before) > 0
    assert len(indexes_before) > 0

    await adb.remove_all_labels()

    constraints = await adb.list_constraints()
    indexes = await adb.list_indexes(exclude_token_lookup=True)

    assert len(constraints) == 0
    assert len(indexes) == 0

    # Recreating all old constraints and indexes
    for constraint in constraints_before:
        constraint_type_clause = "UNIQUE"
        if constraint["type"] == "NODE_PROPERTY_EXISTENCE":
            constraint_type_clause = "NOT NULL"
        elif constraint["type"] == "NODE_KEY":
            constraint_type_clause = "NODE KEY"

        await adb.cypher_query(
            f'CREATE CONSTRAINT {constraint["name"]} FOR (n:{constraint["labelsOrTypes"][0]}) REQUIRE n.{constraint["properties"][0]} IS {constraint_type_clause}'
        )
    for index in indexes_before:
        try:
            await adb.cypher_query(
                f'CREATE INDEX {index["name"]} FOR (n:{index["labelsOrTypes"][0]}) ON (n.{index["properties"][0]})'
            )
        except ClientError:
            pass
