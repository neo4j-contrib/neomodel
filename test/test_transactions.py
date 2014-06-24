from neomodel import db, StructuredNode, StringProperty


class Person(StructuredNode):
    name = StringProperty(unique_index=True)


def test_raw_transaction():
    Person(name='Jimno').save()
    print repr(db.cypher_query("START a=node(*) RETURN a"))
    db.begin()
    print repr(db.cypher_query("START a=node(*) RETURN a"))
    db.commit()
