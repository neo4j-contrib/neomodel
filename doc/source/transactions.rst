============
Transactions
============

This section outlines the way neomodel handles transaction management. For a 
thorough background on how the Neo4J DBMS handles sessions and transactions, 
please refer to `the documentation <https://neo4j.com/docs/operations-manual/
current/clustering/introduction/#causal-clustering-read-replicas>`_.


Basic usage
-----------

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


Explicit Transactions
---------------------

Neomodel also supports  `explicit transactions <https://neo4j.com/docs/
api/python-driver/current/transactions.html>`_ that are pre-designated as either *read* or *write*. 

This is vital when using neomodel over a `Neo4J causal cluster <https://neo4j.com/docs/
operations-manual/current/clustering/>`_ because internally, queries will be rerouted to different 
servers depending on their designation. 

Note here that this functionality is enabled when `bolt+routing:// <https://neo4j.com/docs/
developer-manual/current/drivers/client-applications/#routing_drivers_bolt_routing>`_ has been 
specified as the scheme of the connection URL, as opposed to :code:`bolt://` which 
is more common in single instance deployments.

Read transactions do not modify the database state and therefore only include CYPHER operations that 
simply return results. Write transactions however **do modify the database state** and therefore 
include all CYPHER operations that can potentially Create, Update or Delete Nodes and / or Relationships. 

*By default, starting a transaction without explicitly specifying its type, results in a* **WRITE** 
*transaction*.

Similarly to `Basic Usage`_, Neomodel designates transactions in the following ways:

With distinct context managers::

    with db.read_transaction:
        ...
        
    with db.write_transaction:
        ...
        
    with db.transaction:
        # This designates the transaction as WRITE even if 
        # the the enclosed block of code will not modify the 
        # database state.
        

With function decorators::

    @db.write_transaction
    def update_user_name(uid, name):
        user = Person.nodes.filter(uid=uid)[0]
        user.name = name
        user.save()
        
    @db.read_transaction
    def get_all_users():
        return Person.nodes.all()
        
    @db.transaction # By default a WRITE transaction
    ...
        

With explicit designation::

    db.begin("WRITE")
    ...
    db.begin("READ")
    ...
    db.begin() # By default a **WRITE** transaction

Bookmarks
---------
Neomodel also supports bookmarks. When using neomodel over a `Neo4J causal cluster <https://neo4j.com/docs/
operations-manual/current/clustering/>`_ there is no guarantee that a read will see all of the data
from an earlier committed write transaction. Each transaction returns a bookmark that identifies the transaction.
When starting a new transaction one or more bookmarks may be passed in and the read will not complete until data
from all of the bookmarked transactions is available.

With context managers one or more bookmarks may be set in the transaction before entering the context manager and
the resulting bookmark may be extracted only after the context manager has exited successfully::

    transaction = db.transaction
    transaction.bookmarks = [bookmark1, bookmark2]
    with transaction:
        # All database access happens after completion of the transactions
        # listed in bookmark1 and bookmark2

    bookmark = transaction.last_bookmark

Bookmarks are strings and may be passed between processes. ``transaction.bookmarks`` may be set to a single bookmark,
a sequence of bookmarks, or None.

With function decorators use the ``with_bookmarks`` attribute on the transaction. The decorator will
accept an optional ``bookmarks`` keyword-only parameter with the bookmarks to be passed in to the transaction.
This parameter is removed and not passed to the decorated function.
Any returned value from the decorated function becomes the first element of a tuple with the last bookmark as
the second element::

    @db.write_transaction.with_bookmarks
    def update_user_name(uid, name):
        user = Person.nodes.filter(uid=uid)[0]
        user.name = name
        user.save()

    @db.read_transaction.with_bookmarks
    def get_all_users():
        return Person.nodes.all()


    result, bookmark = update_user_name(uid, name)

    users, last_bookmark = get_all_users(bookmarks=[bookmark])
    for user in users:
        ...


or manually::

    db.begin(bookmarks=[bookmark])
    try:
        new_user = Person(name=username, email=email).save()
        send_email(new_user)
        bookmark = db.commit()
    except Exception as e:
        db.rollback()
