from neomodel import db, StructuredNode, StringProperty, UniqueProperty


class Person(StructuredNode):
    name = StringProperty(unique_index=True)


def test_rollback_and_commit_transaction():
    for p in Person.nodes:
        p.delete()

    Person(name='Roger').save()

    db.begin()
    Person(name='Terry S').save()
    db.rollback()

    assert len(Person.nodes) == 1

    db.begin()
    Person(name='Terry S').save()
    db.commit()

    assert len(Person.nodes) == 2


@db.transaction
def in_a_tx(*names):
    for n in names:
        Person(name=n).save()


def test_transaction_decorator():
    for p in Person.nodes:
        p.delete()

    # should work
    in_a_tx('Roger')
    assert True

    # should bail but raise correct error
    try:
        in_a_tx('Jim', 'Roger')
    except UniqueProperty:
        assert True
    else:
        assert False

    assert 'Jim' not in [p.name for p in Person.nodes]


def test_transaction_as_a_context():
    with db.transaction:
        Person(name='Tim').save()

    assert Person.nodes.filter(name='Tim')

    try:
        with db.transaction:
            Person(name='Tim').save()
    except UniqueProperty:
        assert True
    else:
        assert False


def test_query_inside_transaction():
    for p in Person.nodes:
        p.delete()

    with db.transaction:
        Person(name='Alice').save()
        Person(name='Bob').save()

        assert len([p.name for p in Person.nodes]) == 2


def test_set_connection_works():
    assert Person(name='New guy').save()
    from socket import gaierror

    old_url = db.url
    try:
        db.set_connection('bolt://user:password@nowhere:7687')
        assert False  # Shouldnt get here
    except gaierror:
        assert True
        db.set_connection(old_url)
    # set connection back
    assert Person(name='New guy2').save()