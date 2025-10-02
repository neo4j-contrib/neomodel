Configuration
=============

Neomodel provides a modern, type-safe configuration system for connecting to your Neo4j database. This guide covers the recommended approach using the new dataclass-based configuration system (available from version 6.0), with backward compatibility information for existing code.

.. _configuration_options_doc:

Database Connection Setup
-------------------------

The primary way to configure neomodel is to set up your database connection. There are two approaches:

1. **Neomodel-managed connection** (recommended) - Let neomodel handle the driver lifecycle
2. **Self-managed connection** - Provide your own Neo4j driver instance

Neomodel-managed Connection (Recommended)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is the simplest and most common approach. Neomodel will create and manage the Neo4j driver for you.

Basic connection setup::

    from neomodel import get_config
    
    config = get_config()
    config.database_url = 'bolt://neo4j:password@localhost:7687'

You can also set the database name separately::

    config.database_url = 'bolt://neo4j:password@localhost:7687'
    config.database_name = 'mydatabase'

Advanced driver configuration, for example::

    config.connection_timeout = 60.0
    config.max_connection_pool_size = 50
    config.encrypted = True
    config.keep_alive = True

Self-managed Connection
~~~~~~~~~~~~~~~~~~~~~~~

If you need more control over the driver configuration, you can provide your own Neo4j driver::

    from neo4j import GraphDatabase
    from neomodel import get_config
    
    # Create your own driver
    driver = GraphDatabase.driver(
        'bolt://localhost:7687',
        auth=('neo4j', 'password'),
        encrypted=True,
        max_connection_lifetime=3600
    )
    
    # Pass it to neomodel
    config = get_config()
    config.driver = driver

.. note::
    When using a self-managed driver, you are responsible for closing it when your application shuts down.

Modern Configuration System (Version 6.0+)
------------------------------------------

Neomodel 6.0 introduces a modern dataclass-based configuration system with the following benefits:

* **Type Safety**: All configuration values are properly typed
* **Validation**: Configuration values are validated at startup and when changed
* **Environment Variables**: Automatic loading from environment variables
* **IDE Support**: Better autocomplete and type checking

Using the Modern Configuration API
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Access and modify configuration::

    from neomodel import get_config, set_config, reset_config
    
    # Get the current configuration
    config = get_config()
    print(config.database_url)
    print(config.force_timezone)
    
    # Update configuration
    config.update(database_url='bolt://new:url@localhost:7687')
    
    # Set a custom configuration
    from neomodel import NeomodelConfig
    custom_config = NeomodelConfig(
        database_url='bolt://custom:url@localhost:7687',
        force_timezone=True
    )
    set_config(custom_config)
    
    # Reset to defaults (loads from environment variables or defaults)
    reset_config()

Environment Variable Support
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Configuration is automatically loaded from environment variables using the ``NEOMODEL_`` prefix:

* ``NEOMODEL_DATABASE_URL`` - Database connection URL
* ``NEOMODEL_DATABASE_NAME`` - Database name for custom driver
* ``NEOMODEL_CONNECTION_ACQUISITION_TIMEOUT`` - Connection acquisition timeout
* ``NEOMODEL_CONNECTION_TIMEOUT`` - Connection timeout
* ``NEOMODEL_ENCRYPTED`` - Enable encrypted connections
* ``NEOMODEL_KEEP_ALIVE`` - Enable keep-alive connections
* ``NEOMODEL_MAX_CONNECTION_LIFETIME`` - Maximum connection lifetime
* ``NEOMODEL_MAX_CONNECTION_POOL_SIZE`` - Maximum connection pool size
* ``NEOMODEL_MAX_TRANSACTION_RETRY_TIME`` - Maximum transaction retry time
* ``NEOMODEL_USER_AGENT`` - User agent string
* ``NEOMODEL_FORCE_TIMEZONE`` - Force timezone-aware datetime objects
* ``NEOMODEL_SOFT_CARDINALITY_CHECK`` - Enable soft cardinality checking
* ``NEOMODEL_CYPHER_DEBUG`` - Enable Cypher debug logging
* ``NEOMODEL_SLOW_QUERIES`` - Threshold in seconds for slow query logging (0 = disabled)

Example::

    # Set environment variables
    export NEOMODEL_DATABASE_URL='bolt://neo4j:password@localhost:7687'
    export NEOMODEL_FORCE_TIMEZONE='true'
    export NEOMODEL_CONNECTION_TIMEOUT='60.0'
    
    # Configuration will be automatically loaded from environment
    from neomodel import config
    print(config.DATABASE_URL)  # 'bolt://neo4j:password@localhost:7687'
    print(config.FORCE_TIMEZONE)  # True
    print(config.CONNECTION_TIMEOUT)  # 60.0

Configuration Validation
~~~~~~~~~~~~~~~~~~~~~~~~

The configuration system validates values when they are set::

    from neomodel import get_config
    
    config = get_config()
    
    # This will raise a ValueError
    try:
        config.connection_timeout = -1
    except ValueError as e:
        print(f"Validation error: {e}")
    
    # Invalid database URLs are also caught
    try:
        config.database_url = "invalid-url"
    except ValueError as e:
        print(f"Validation error: {e}")

Legacy Configuration (Backward Compatibility)
---------------------------------------------

.. note::
    The following section describes the legacy configuration approach, available in neomodel 5.5.3 and earlier.
    While still supported for backward compatibility, we recommend using the modern configuration system described above.

For existing code, the traditional uppercase configuration attributes are still available::

    from neomodel import config
    
    # Legacy approach (still works)
    config.DATABASE_URL = 'bolt://neo4j:neo4j@localhost:7687'
    config.MAX_CONNECTION_POOL_SIZE = 100
    config.CONNECTION_ACQUISITION_TIMEOUT = 60.0
    config.CONNECTION_TIMEOUT = 30.0
    config.ENCRYPTED = False
    config.KEEP_ALIVE = True
    config.MAX_CONNECTION_LIFETIME = 3600
    config.MAX_TRANSACTION_RETRY_TIME = 30.0
    config.RESOLVER = None
    config.TRUST = neo4j.TRUST_SYSTEM_CA_SIGNED_CERTIFICATES
    config.USER_AGENT = 'neomodel/v5.5.1'

Setting the database name with legacy approach::

    # Using the URL only
    config.DATABASE_URL = 'bolt://neo4j:neo4j@localhost:7687/mydb'
    
    # Using config option
    config.DATABASE_URL = 'bolt://neo4j:neo4j@localhost:7687'
    config.DATABASE_NAME = 'mydb'

Legacy self-managed driver setup::
    
    from neo4j import GraphDatabase
    my_driver = GraphDatabase().driver('bolt://localhost:7687', auth=('neo4j', 'password'))
    config.DRIVER = my_driver

.. note::
    Only the synchronous driver works with the legacy self-managed approach. For async drivers, use the modern configuration system.

Managing Connections
--------------------

Changing Connections
~~~~~~~~~~~~~~~~~~~~

You can change the connection at any time using the modern configuration API::

    from neomodel import get_config
    
    config = get_config()
    config.database_url = 'bolt://new:url@localhost:7687'

    # Using self-managed driver
    db.set_connection(driver=my_driver)

Or using the legacy approach::

    from neomodel import db
    # Using URL - auto-managed
    db.set_connection(url='bolt://neo4j:neo4j@localhost:7687')

Closing Connections
~~~~~~~~~~~~~~~~~~~

Since Neo4j version 5, driver auto-close is deprecated. Make sure to close the connection when your application shuts down::

    from neomodel import db
    db.close_connection()

This will close the Neo4j driver and clean up neomodel's internal resources.

Security Best Practices
-----------------------

Protect Your Credentials
~~~~~~~~~~~~~~~~~~~~~~~~

You should `avoid setting database access credentials in plain sight <https://
www.ndss-symposium.org/wp-content/uploads/2019/02/ndss2019_04B-3_Meli_paper.pdf>`_. 

**Recommended approach using environment variables**::

    # Set environment variables
    export NEOMODEL_DATABASE_URL='bolt://neo4j:password@localhost:7687'
    
    # Configuration automatically loads from environment
    from neomodel import get_config
    config = get_config()


Additional Configuration Options
--------------------------------

Force Timezone on DateTime Properties
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Ensure all DateTimes are provided with a timezone before being serialized to UTC epoch::

    from neomodel import get_config
    
    config = get_config()
    config.force_timezone = True  # default False

Enable Soft Cardinality Checking
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Enable warnings instead of errors for relationship cardinality violations::

    config.soft_cardinality_check = True  # default False

Enable Cypher Debug Logging
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Log all Cypher queries for debugging::

    config.cypher_debug = True  # default False

Enable Slow Query Logging
~~~~~~~~~~~~~~~~~~~~~~~~~

Log queries that take longer than the specified threshold::

    config.slow_queries = 1.0  # Log queries taking more than 1 second

Index and Constraint Management
-------------------------------

Neomodel provides the :ref:`neomodel_install_labels` script for automatic index and constraint creation.

Install indexes and constraints for a single class::

    from neomodel import install_labels
    install_labels(YourClass)

Or for an entire schema::

    import yourapp  # make sure your app is loaded
    from neomodel import install_all_labels

    install_all_labels()
    # Output:
    # Setting up labels and constraints...
    # Found yourapp.models.User
    # + Creating unique constraint for name on label User for class yourapp.models.User
    # ...

.. note::
    ``config.AUTO_INSTALL_LABELS`` has been removed from neomodel in version 5.3
