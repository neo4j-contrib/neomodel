======================
Neomodel documentation
======================

An Object Graph Mapper (OGM) for the Neo4j_ graph database, built on the awesome neo4j_driver_

- Familiar Django model style definitions.
- Powerful query API.
- Enforce your schema through cardinality restrictions.
- Full transaction support.
- Thread safe.
- Async support.
- pre/post save/delete hooks.
- Django integration via django_neomodel_

.. _neo4j: https://www.neo4j.org
.. _neo4j_driver: https://github.com/neo4j/neo4j-python-driver
.. _django_neomodel: https://github.com/neo4j-contrib/django-neomodel

Requirements
============

For releases 5.x :

- Python 3.7+
- neo4j 5.x, 4.4 (LTS)

For releases 4.x :

- Python 3.7 -> 3.10
- Neo4j 4.x (including 4.4 LTS for neomodel version 4.0.10)

Installation
============

Install from pypi (recommended)::

    $ pip install neomodel

To install from github::

    $ pip install git+git://github.com/neo4j-contrib/neomodel.git@HEAD#egg=neomodel-dev

.. attention::

    **New in 6.0**

    From now on, neomodel will use SemVer (major.minor.patch) for versioning.

    This version introduces a modern configuration system, using a dataclass with typing, runtime and update validation rules, and environment variables support.
    See the :ref:`configuration_options_doc` section for more details.

    This version introduces the merge_by parameter for batch operations to customize merge behaviour (label and property keys).
    See the :ref:`batch` section for more details.

    **Breaking changes in 6.0**

    - The soft cardinality check is now available for all cardinalities, and strict check is enabled by default.
    - AsyncDatabase / Database are now true singletons for clarity
    - Standalone methods moved into the Database() class have been removed outside of the Database() class :
        - change_neo4j_password
        - clear_neo4j_database
        - drop_constraints
        - drop_indexes
        - remove_all_labels
        - install_labels
        - install_all_labels
    - Note : to call these methods with async, use the ones in the AsyncDatabase() _adb_ singleton.


Contents
========

.. toctree::
   :maxdepth: 2

   getting_started
   relationships
   properties
   spatial_properties
   schema_management
   filtering_ordering
   traversal
   advanced_query_operations
   semantic_indexes
   cypher
   transactions
   hooks
   batch
   configuration
   extending
   module_documentation
   module_documentation_sync
   module_documentation_async

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
