Configuration
=============

This section is covering the Neomodel 'config' module and its variables.

.. _connection_options_doc:

Connection
----------

There are two ways to define your connection to the database :

1. Provide a Neo4j URL and some options - Driver will be managed by neomodel
2. Create your own Neo4j driver and pass it to neomodel

neomodel-managed (default)
--------------------------

Set the connection URL::

    config.DATABASE_URL = 'bolt://neo4j:neo4j@localhost:7687`

Adjust driver configuration - these options are only available for this connection method::

    config.MAX_CONNECTION_POOL_SIZE = 100  # default
    config.CONNECTION_ACQUISITION_TIMEOUT = 60.0  # default
    config.CONNECTION_TIMEOUT = 30.0  # default
    config.ENCRYPTED = False  # default
    config.KEEP_ALIVE = True  # default
    config.MAX_CONNECTION_LIFETIME = 3600  # default
    config.MAX_CONNECTION_POOL_SIZE = 100  # default
    config.MAX_TRANSACTION_RETRY_TIME = 30.0  # default
    config.RESOLVER = None  # default
    config.TRUST = neo4j.TRUST_SYSTEM_CA_SIGNED_CERTIFICATES  # default
    config.USER_AGENT = neomodel/v5.4.5  # default

Setting the database name, if different from the default one::

    # Using the URL only
    config.DATABASE_URL = 'bolt://neo4j:neo4j@localhost:7687/mydb`

    # Using config option
    config.DATABASE_URL = 'bolt://neo4j:neo4j@localhost:7687`
    config.DATABASE_NAME = 'mydb'

self-managed
------------

Create a Neo4j driver::
    
    from neo4j import GraphDatabase
    my_driver = GraphDatabase().driver('bolt://localhost:7687', auth=('neo4j', 'password'))
    config.DRIVER = my_driver

See the `driver documentation <https://neo4j.com/docs/api/python-driver/current/api.html#graphdatabase>` here.

This mode allows you to use all the available driver options that neomodel doesn't implement, for example auth tokens for SSO.
Note that you have to manage the driver's lifecycle yourself.

However, everything else is still handled by neomodel : sessions, transactions, etc...

NB : Only the synchronous driver will work in this way. See the next section for the preferred method, and how to pass an async driver instance.

Change/Close the connection
---------------------------

Optionally, you can change the connection at any time by calling ``set_connection``::

    from neomodel import db
    # Using URL - auto-managed
    db.set_connection(url='bolt://neo4j:neo4j@localhost:7687')

    # Using self-managed driver
    db.set_connection(driver=my_driver)

The new connection url will be applied to the current thread or process.

Since Neo4j version 5, driver auto-close is deprecated. Make sure to close the connection anytime you want to replace it,
as well as at the end of your application's lifecycle by calling ``close_connection``::

    from neomodel import db
    db.close_connection()

    # If you then want a new connection
    db.set_connection(url=url)

This will close the Neo4j driver, and clean up everything that neomodel creates for its internal workings.

Protect your credentials
------------------------

You should `avoid setting database access credentials in plain sight <https://
www.ndss-symposium.org/wp-content/uploads/2019/02/ndss2019_04B-3_Meli_paper.pdf>`_. Neo4J defines a number of
`environment variables <https://neo4j.com/developer/kb/how-do-i-authenticate-with-cypher-shell-without-specifying-the-
username-and-password-on-the-command-line/>`_ that are used in its tools and these can be re-used for other applications
too.

These are:

* ``NEO4J_USERNAME``
* ``NEO4J_PASSWORD``
* ``NEO4J_BOLT_URL``

By setting these with (for example): ::

    $ export NEO4J_USERNAME=neo4j
    $ export NEO4J_PASSWORD=neo4j
    $ export NEO4J_BOLT_URL="bolt://$NEO4J_USERNAME:$NEO4J_PASSWORD@localhost:7687"

They can be accessed from a Python script via the ``environ`` dict of module ``os`` and be used to set the connection
with something like: ::

    import os
    from neomodel import config

    config.DATABASE_URL = os.environ["NEO4J_BOLT_URL"]


Enable automatic index and constraint creation
----------------------------------------------

Neomodel provides the :ref:`neomodel_install_labels` script for this task,
however if you want to handle this manually see below.

Install indexes and constraints for a single class::

    from neomodel import install_labels
    install_labels(YourClass)

Or for an entire 'schema' ::

    import yourapp  # make sure your app is loaded
    from neomodel import install_all_labels

    install_all_labels()
    # Output:
    # Setting up labels and constraints...
    # Found yourapp.models.User
    # + Creating unique constraint for name on label User for class yourapp.models.User
    # ...

.. note::
    config.AUTO_INSTALL_LABELS has been removed from neomodel in version 5.3

Require timezones on DateTimeProperty
-------------------------------------

Ensure all DateTimes are provided with a timezone before being serialised to UTC epoch::

    config.FORCE_TIMEZONE = True  # default False
