Transactions
------------
transactions can be used via a context manager::

    from neomodel import db

    with db.transaction:
        Person(name='Bob').save()

or as a function decorator::

    @db.transaction
    def update_user_name(uid, name):
        user = Person.nodes.filter(uid=uid)[0]
        user.name = name
        user.save()

Transactions are local to the thread as is the `db` object (see `threading.local`).
