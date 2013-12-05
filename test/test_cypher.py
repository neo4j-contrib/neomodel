from neomodel import StructuredNode, StringProperty, CypherException


class User2(StructuredNode):
    email = StringProperty()


def test_cypher():
    """
    py2neo's cypher result format changed in 1.6 this tests its return value
    is backward compatible with earlier versions of neomodel
    """

    jim = User2(email='jim1@test.com').save()
    data, meta = jim.cypher("START a=node({self}) RETURN a.email")
    assert data[0][0] == 'jim1@test.com'
    assert 'a.email' in meta

    data, meta = jim.cypher("START a=node({self}) MATCH (a)<-[:USER2]-(b) RETURN a, b, 3")
    assert 'a' in meta and 'b' in meta


def test_cypher_syntax_error():
    jim = User2(email='jim1@test.com').save()
    try:
        jim.cypher("START a=node({self}) RETURN xx")
    except CypherException as e:
        assert hasattr(e, 'message')
        assert hasattr(e, 'query')
        assert hasattr(e, 'query_parameters')
        assert hasattr(e, 'java_trace')
        assert hasattr(e, 'java_exception')
    else:
        assert False
