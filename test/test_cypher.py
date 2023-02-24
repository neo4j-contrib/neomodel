import itertools

from neomodel import StructuredNode, StringProperty, RelationshipTo
from neo4j.exceptions import ClientError as CypherError


class User2(StructuredNode):
    email = StringProperty()

class Animal(StructuredNode):
    name = StringProperty()

def test_cypher():
    """
    test result format is backward compatible with earlier versions of neomodel
    """

    jim = User2(email='jim1@test.com').save()
    data, meta = jim.cypher("MATCH (a) WHERE id(a)=$self RETURN a.email")
    assert data[0][0] == 'jim1@test.com'
    assert 'a.email' in meta

    data, meta = jim.cypher("MATCH (a) WHERE id(a)=$self"
                            " MATCH (a)<-[:USER2]-(b) "
                            "RETURN a, b, 3")
    assert 'a' in meta and 'b' in meta


def test_cypher_syntax_error():
    jim = User2(email='jim1@test.com').save()
    try:
        jim.cypher("MATCH a WHERE id(a)={self} RETURN xx")
    except CypherError as e:
        assert hasattr(e, 'message')
        assert hasattr(e, 'code')
    else:
        assert False, "CypherError not raised."

def test_cypher_resolve_objects():
    jim = User2(email='jim1@test.com').save()
    cat = Animal(name='jim\'s cat').save()

    data, meta = jim.cypher("MATCH (a) WHERE id(a)=$self OR id(a)=$cat RETURN a", {'cat': cat.id}, resolve_objects=True)
    # flatten the data (otherwise we have lists of lists)
    data = list(itertools.chain(*data))
    assert len(data) == 2

    assert any(isinstance(thing, User2) for thing in data)
    assert any(isinstance(thing, Animal) for thing in data)
