Configuration
=============

Covering the neomodel 'config' module and its variables.

Disabling automatic index and constraint creation
-------------------------------------------------

After a StructuredNode class definition neomodel installs the corresponding constraints and indexes at compile time.
This can be annoying when unit testing.

You can disable this feature by setting the follow var (prior to loading your class definitions::

    from neomodel import config
    config.AUTO_INSTALL_LABELS = False

If you wish to manually install a nodes indexes and constraints::

    from neomodel import install_labels
    install_labels(YourClass)

