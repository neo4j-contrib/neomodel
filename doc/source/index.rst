======================
Neomodel documentation
======================

An Object Graph Mapper (OGM) for the Neo4j_ graph database, built on the awesome neo4j_driver_

- Familiar Django model style definitions.
- Powerful query API.
- Enforce your schema through cardinality restrictions.
- Full transaction support.
- Thread safe.
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


Contents
========

.. toctree::
   :maxdepth: 2

   getting_started
   relationships
   properties
   spatial_properties
   queries
   cypher
   transactions
   hooks
   batch
   configuration
   extending
   module_documentation

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
