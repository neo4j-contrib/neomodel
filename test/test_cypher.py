from neo4j.exceptions import ClientError as CypherError

from neomodel import StringProperty, StructuredNode
from neomodel.core import db


class User2(StructuredNode):
    email = StringProperty()


def test_cypher():
    """
    test result format is backward compatible with earlier versions of neomodel
    """

    jim = User2(email="jim1@test.com").save()
    data, meta = jim.cypher(
        f"MATCH (a) WHERE {db.get_id_method()}(a)=$self RETURN a.email"
    )
    assert data[0][0] == "jim1@test.com"
    assert "a.email" in meta

    data, meta = jim.cypher(
        f"""
            MATCH (a) WHERE {db.get_id_method()}(a)=$self
            MATCH (a)<-[:USER2]-(b)
            RETURN a, b, 3
        """
    )
    assert "a" in meta and "b" in meta


def test_cypher_syntax_error():
    jim = User2(email="jim1@test.com").save()
    try:
        jim.cypher(f"MATCH a WHERE {db.get_id_method()}(a)={{self}} RETURN xx")
    except CypherError as e:
        assert hasattr(e, "message")
        assert hasattr(e, "code")
    else:
        assert False, "CypherError not raised."
