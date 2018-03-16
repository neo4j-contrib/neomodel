Transactions
------------

Transactions can be used via a context manager::

    from neomodel import db

    with db.client.transaction:
        Person(name='Bob').save()

or as a function decorator::

    @db.client.transaction
    def update_user_name(uid, name):
        user = Person.nodes.filter(uid=uid)[0]
        user.name = name
        user.save()

or manually::

    db.client.begin()
    try:
        new_user = Person(name=username, email=email).save()
        send_email(new_user)
        db.client.commit()
    except Exception as e:
        db.client.rollback()

Transactions are local to the thread as is the `db.client` object (see :class:`py3:threading.local`).
If your using celery or another task scheduler its advised to wrap each task within a transaction::

    @task
    @db.client.transaction  # comes after the task decorator
    def send_email(user):
        ...
