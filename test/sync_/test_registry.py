from test._async_compat import mark_sync_test

from pytest import raises, skip

from neomodel import StringProperty, StructuredNode, db, get_config
from neomodel.exceptions import NodeClassAlreadyDefined, NodeClassNotDefined


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

    config = get_config()
    # Now, we will test object resolution
    db.close_connection()
    db.set_connection(url=f"{config.database_url}/{db_one}")
    db.clear_neo4j_database()
    patient1 = PatientOne(name="patient1").save()
    patients, _ = db.cypher_query("MATCH (n:Patient) RETURN n", resolve_objects=True)
    # This means that the auto object resolution is working
    assert patients[0][0] == patient1

    db.close_connection()
    db.set_connection(url=f"{config.database_url}/{db_two}")
    db.clear_neo4j_database()
    patient2 = PatientTwo(identifier="patient2").save()
    patients, _ = db.cypher_query("MATCH (n:Patient) RETURN n", resolve_objects=True)
    assert patients[0][0] == patient2

    db.close_connection()
    db.set_connection(url=config.database_url)


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


@mark_sync_test
def test_allow_reload_flag():
    """Test that __allow_reload__ flag allows redefining classes without raising an exception."""
    import warnings

    # First, define a class with allow_reload enabled
    class ReloadableNode(StructuredNode):
        __label__ = "ReloadableNode"
        __allow_reload__ = True
        name = StringProperty()

    # Now redefine the same class - this should issue a warning but not raise an exception
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        class ReloadableNode(StructuredNode):  # noqa: F811
            __label__ = "ReloadableNode"
            __allow_reload__ = True
            name = StringProperty()
            email = StringProperty()  # Add a new property

        # Verify a warning was issued
        assert len(w) == 1
        assert issubclass(w[0].category, UserWarning)
        assert "is being reloaded" in str(w[0].message)
        assert "ReloadableNode" in str(w[0].message)


@mark_sync_test
def test_allow_reload_without_flag():
    """Test that without __allow_reload__, redefining raises NodeClassAlreadyDefined."""

    class NonReloadableNode(StructuredNode):
        __label__ = "NonReloadableNode"
        name = StringProperty()

    # Attempting to redefine should raise an exception
    with raises(NodeClassAlreadyDefined):

        class NonReloadableNode(StructuredNode):  # noqa: F811
            __label__ = "NonReloadableNode"
            email = StringProperty()


@mark_sync_test
def test_allow_reload_with_target_databases():
    """Test that __allow_reload__ works with database-specific classes."""
    if not db.edition_is_enterprise():
        skip("Skipping test for community edition")

    import warnings

    db_test = "testreloaddb"
    db.cypher_query(f"CREATE DATABASE {db_test} IF NOT EXISTS")

    # Define a class for a specific database with allow_reload
    class ReloadablePatient(StructuredNode):
        __label__ = "ReloadablePatient"
        __target_databases__ = [db_test]
        __allow_reload__ = True
        name = StringProperty()

    # Redefine the same class - should warn but not raise
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        class ReloadablePatient(StructuredNode):  # noqa: F811
            __label__ = "ReloadablePatient"
            __target_databases__ = [db_test]
            __allow_reload__ = True
            identifier = StringProperty()

        # Verify a warning was issued
        assert len(w) == 1
        assert issubclass(w[0].category, UserWarning)
        assert "is being reloaded for database" in str(w[0].message)
        assert db_test in str(w[0].message)
