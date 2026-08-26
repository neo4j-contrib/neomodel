import warnings
from test._async_compat import mark_sync_test

from pytest import raises, skip

from neomodel import StringProperty, StructuredNode, db, get_config
from neomodel.exceptions import NodeClassAlreadyDefined, NodeClassNotDefined
from neomodel.sync_._registry import registry


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

    # Reaching this point without failing means the database-specific registry
    # allows reuse of the same label ("Patient") in different databases.
    # (Genuine same-label clashes - two distinct classes for the same label in
    # the same scope - are now reported at resolution time; see
    # test_duplicate_labels_raise_on_resolution.)

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
def test_class_redefinition_is_allowed():
    """Redefining a class (e.g. on hot reload) no longer raises: node classes are
    discovered from the live hierarchy, so the latest definition simply wins."""

    class ReloadableNode(StructuredNode):
        __label__ = "ReloadableNode"
        name = StringProperty()

    # Redefining the same class must not raise (previously required allow_reload).
    class ReloadableNode(StructuredNode):  # noqa: F811
        __label__ = "ReloadableNode"
        name = StringProperty()
        email = StringProperty()  # a new property on the latest definition

    node = ReloadableNode(name="reloaded", email="who@where.com").save()
    resolved, _ = db.cypher_query(
        "MATCH (n:ReloadableNode) RETURN n", resolve_objects=True
    )
    # The latest definition (with the extra property) is used for resolution.
    assert resolved[0][0] == node
    assert hasattr(resolved[0][0], "email")


@mark_sync_test
def test_allow_reload_is_deprecated():
    """config.allow_reload is a deprecated no-op that warns when set."""
    neomodel_config = get_config()
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        neomodel_config.allow_reload = True
    try:
        assert any(
            issubclass(w.category, DeprecationWarning)
            and "allow_reload" in str(w.message)
            for w in recorded
        )
    finally:
        neomodel_config.allow_reload = False


@mark_sync_test
def test_duplicate_labels_raise_on_resolution():
    """Two distinct live classes claiming the same labels are reported as a
    NodeClassAlreadyDefined when a matching node is resolved (not at definition)."""

    class OriginalDup(StructuredNode):
        __label__ = "DupResolutionLabel"
        name = StringProperty()

    # A genuinely different class (not a reload) claiming the same label.
    class ConflictingDup(StructuredNode):
        __label__ = "DupResolutionLabel"
        title = StringProperty()

    db.cypher_query("CREATE (:DupResolutionLabel {name: 'x'})")
    with raises(
        NodeClassAlreadyDefined,
        match=r"Class .* with labels .* already defined:.*",
    ):
        db.cypher_query("MATCH (n:DupResolutionLabel) RETURN n", resolve_objects=True)


@mark_sync_test
def test_class_redefinition_with_target_databases():
    """Redefining a database-specific class is likewise allowed; the latest
    definition wins in that database's registry."""
    if not db.edition_is_enterprise():
        skip("Skipping test for community edition")

    db_test = "testreloaddb"
    db.cypher_query(f"CREATE DATABASE {db_test} IF NOT EXISTS")

    class ReloadablePatient(StructuredNode):
        __label__ = "ReloadablePatient"
        __target_databases__ = [db_test]
        name = StringProperty()

    # Redefining the database-specific class must not raise.
    class ReloadablePatient(StructuredNode):  # noqa: F811
        __label__ = "ReloadablePatient"
        __target_databases__ = [db_test]
        identifier = StringProperty()  # a new property on the latest definition

    resolved = registry.get_class(frozenset(["ReloadablePatient"]), db_test)
    assert resolved is not None
    assert "identifier" in dict(resolved.__all_properties__)
