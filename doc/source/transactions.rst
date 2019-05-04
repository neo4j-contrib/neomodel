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

Neomodel also supports  `epxlicit transactions <https://neo4j.com/docs/
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
        
    @db.trasaction # Be default a WRITE transaction
    ...
        

With explicit designation::

    db.begin("WRITE")
    ...
    db.begin("READ")
    ...
    db.begin() # By default a **WRITE** transaction
