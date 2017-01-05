Configuration
=============

Covering the neomodel 'config' module and its variables.

Database url
------------

Set your connection details::

    config.DATABASE_URL = 'bolt://neo4j:neo4j@localhost:7687`

Disable automatic index and constraint creation
-----------------------------------------------

After a StructuredNode class definition neomodel installs the corresponding constraints and indexes at compile time.
This can be annoying for unit testing and may result in deadlocks when used with gunicorn.

You can disable this feature by setting the follow var (prior to loading your class definitions)::

    from neomodel import config
    config.AUTO_INSTALL_LABELS = False

If you wish to manually install a nodes indexes and constraints you may do it on a per class basis::

    from neomodel import install_labels
    install_labels(YourClass)

Or for your entire 'schema' ::

    import yourapp  # make sure your app is loaded
    from neomodel import install_all_labels

    install_all_labels()
    # Output:
    # Setting up labels and constraints...
    # + Creating unique constraint for name on label User for class yourapp.models.User
    # yourapp.models.User done.

You may want to build this into your deployment mechanism.

