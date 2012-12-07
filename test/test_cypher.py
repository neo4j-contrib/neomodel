from neomodel import StructuredNode, StringProperty, CypherException


class User2(StructuredNode):
    email = StringProperty()


def test_cypher():
    jim = User2(email='jim1@test.com').save()
    email = jim.cypher("START a=node({self}) RETURN a.email")[0][0][0]
    assert email == 'jim1@test.com'


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
