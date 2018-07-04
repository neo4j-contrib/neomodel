Transactions
------------
Transactions can be used via a context manager::

    from neomodel import db

    with db.transaction:
        Person(name='Bob').save()

or as a function decorator::

    @db.transaction
    def update_user_name(uid, name):
        user = Person.nodes.filter(uid=uid)[0]
        user.name = name
        user.save()

or manually::

    db.begin()
    try:
        new_user = Person(name=username, email=email).save()
        send_email(new_user)
        db.commit()
    except Exception as e:
        db.rollback()

Transactions are local to the thread as is the `db` object (see `threading.local`).
If you're using celery or another task scheduler it's advised to wrap each task within a transaction::

    @task
    @db.transaction  # comes after the task decorator
    def send_email(user):
        ...

Transactions can also be designated as *write transactions*.
Marking as a write transaction may not matter on a single-instance Neo4J, but is vital in a Neo4J causal cluster where writes must be sent to the leader node.
For performance purposes, this should be limited to transactions that write/delete data, or any situation where talking to the leader node is essential::

    @db.write_transaction
    def update_user_name(uid, name):
        user = Person.nodes.filter(uid=uid)[0]
        user.name = name
        user.save()
