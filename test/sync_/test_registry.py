from test._async_compat import mark_sync_test

from pytest import raises, skip

from neomodel import (
    DateProperty,
    IntegerProperty,
    RelationshipTo,
    StringProperty,
    StructuredNode,
    StructuredRel,
    config,
    db,
)
from neomodel.exceptions import (
    NodeClassAlreadyDefined,
    NodeClassNotDefined,
    RelationshipClassRedefined,
)


@mark_sync_test
def test_db_specific_node_labels():
    if not db.edition_is_enterprise():
        skip("Skipping test for community edition")
    db_one = "one"
    db_two = "two"
    db.cypher_query(f"CREATE DATABASE {db_one} IF NOT EXISTS")
    db.cypher_query(f"CREATE DATABASE {db_two} IF NOT EXISTS")

    class Experiment(StructuredNode):
        __label__ = "Experiment"
        name = StringProperty()

    class PatientOne(StructuredNode):
        __label__ = "Patient"
        __target_databases__ = [db_one]
        name = StringProperty()

    class PatientTwo(StructuredNode):
        __label__ = "Patient"
        __target_databases__ = [db_two]
        identifier = StringProperty()

    # This should have reached this point without failing
    # It means db specific registry is allowing reuse of labels in different databases
    # Next test will check if the standard registry still denies reuse of labels
    with raises(NodeClassAlreadyDefined):

        class ExperimentTwo(StructuredNode):
            __label__ = "Experiment"
            name = StringProperty()

        ExperimentTwo(name="experiment2").save()

    # Finally, this tests that db specific registry denies reuse of labels in the same db
    with raises(NodeClassAlreadyDefined):

        class PatientOneBis(StructuredNode):
            __label__ = "Patient"
            __target_databases__ = [db_one]
            name = StringProperty()

        PatientOneBis(name="patient1.2").save()

    # Now, we will test object resolution
    db.close_connection()
    db.set_connection(url=f"{config.DATABASE_URL}/{db_one}")
    db.clear_neo4j_database()
    patient1 = PatientOne(name="patient1").save()
    patients, _ = db.cypher_query("MATCH (n:Patient) RETURN n", resolve_objects=True)
    # This means that the auto object resolution is working
    assert patients[0][0] == patient1

    db.close_connection()
    db.set_connection(url=f"{config.DATABASE_URL}/{db_two}")
    db.clear_neo4j_database()
    patient2 = PatientTwo(identifier="patient2").save()
    patients, _ = db.cypher_query("MATCH (n:Patient) RETURN n", resolve_objects=True)
    assert patients[0][0] == patient2

    db.close_connection()
    db.set_connection(url=config.DATABASE_URL)


@mark_sync_test
def test_resolution_not_defined_class():
    if not db.edition_is_enterprise():
        skip("Skipping test for community edition")

    class PatientX(StructuredNode):
        __label__ = "Patient"
        __target_databases__ = ["db_x"]
        name = StringProperty()

    db.cypher_query("CREATE (n:Gabagool)")
    with raises(
        NodeClassNotDefined,
        match=r"Node with labels Gabagool does not resolve to any of the known objects[\s\S]*Database-specific: db_x.*",
    ):
        _ = db.cypher_query("MATCH (n:Gabagool) RETURN n", resolve_objects=True)
