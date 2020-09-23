Configuration
=============

This section is covering the Neomodel 'config' module and its variables.

Database
--------

Seting the connection URL::

    config.DATABASE_URL = 'bolt://neo4j:neo4j@localhost:7687`

Disable encrypted connection (usefult for development)::

    config.ENCRYPTED_CONNECTION = False

Adjust connection pool size::

    config.MAX_CONNECTION_POOL_SIZE = 50  # default

Enable automatic index and constraint creation
----------------------------------------------

After the definition of a `StructuredNode`, Neomodel can install the corresponding 
constraints and indexes at compile time. However this method is only recommended for testing::

    from neomodel import config
    # before loading your node definitions
    config.AUTO_INSTALL_LABELS = True

Neomodel also provides the `neomodel_install_labels` scripr for this task, 
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

Require timezones on DateTimeProperty
-------------------------------------

Ensure all DateTimes are provided with a timezone before being serialised to UTC epoch::

    config.FORCE_TIMEZONE = True  # default False
