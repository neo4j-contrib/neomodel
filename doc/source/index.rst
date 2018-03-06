======================
Neomodel documentation
======================

An Object Graph Mapper (OGM) for the neo4j_ graph database, built on the awesome neo4j_driver_

- Familiar Django model style definitions.
- Powerful query API.
- Enforce your schema through cardinality restrictions.
- Full transaction support.
- Thread safe.
- pre/post save/delete hooks.
- Django integration via django_neomodel_

.. _neo4j: https://www.neo4j.org
.. _neo4j_driver: https://github.com/neo4j/neo4j-python-driver
.. _django_neomodel: https://github.com/robinedwards/django-neomodel

Requirements
============

- Python 2.7, 3.3+
- neo4j 3.0, 3.1, 3.2

Installation
============

Install from pypi (recommended)::

    $ pip install neomodel

To install from github::

    $ pip install git+git://github.com/robinedwards/neomodel.git@HEAD#egg=neomodel-dev


Contents
========

.. toctree::
   :maxdepth: 2

   getting_started
   relationships
   properties
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
