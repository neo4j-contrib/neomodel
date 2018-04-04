.. image:: https://raw.githubusercontent.com/neo4j-contrib/neomodel/master/doc/source/_static/neomodel-300.png
   :alt: neomodel

An Object Graph Mapper (OGM) for the neo4j_ graph database, built on the awesome neo4j_driver_

- Familiar Django model style definitions.
- Powerful query API.
- Enforce your schema through cardinality restrictions.
- Full transaction support.
- Thread safe.
- pre/post save/delete hooks.
- Django integration via django_neomodel_

.. _django_neomodel: https://github.com/neo4j-contrib/django-neomodel
.. _neo4j: https://neo4j.com/
.. _neo4j_driver: https://github.com/neo4j/neo4j-python-driver

.. image:: https://secure.travis-ci.org/neo4j-contrib/neomodel.png
    :target: https://secure.travis-ci.org/neo4j-contrib/neomodel/

.. image:: https://readthedocs.org/projects/neomodel/badge/?version=latest
    :alt: Documentation Status
    :scale: 100%
    :target: https://neomodel.readthedocs.io/en/latest/?badge=latest

Documentation
=============

Available on readthedocs_.

.. _readthedocs: http://neomodel.readthedocs.org

Requirements
============

- Python 2.7, 3.4+
- neo4j 3.0, 3.1, 3.2, 3.3

Installation
============

Install from pypi (recommended)::

    $ pip install neomodel

To install from github::

    $ pip install git+git://github.com/neo4j-contrib/neomodel.git@HEAD#egg=neomodel-dev

Upgrading 2.x to 3.x
====================

 * Now utilises neo4j_driver as the backend which uses bolt so neo4j 3 is required
 * Connection now set through config.DATABASE_URL (see getting started docs)
 * The deprecated category() method on StructuredNode has been removed
 * The deprecated index property on StructuredNode has been removed
 * The streaming=True flag is now irrelevant with bolt and produces a deprecation warning
 * Batch operations must now be wrapped in a transaction in order to be atomic
 * Indexing NodeSets returns a single node now as opposed to a list

Contributing
============

Ideas, bugs, tests and pull requests always welcome.

Running the test suite
----------------------

Make sure you have a Neo4j database version 3 or higher to run the tests on. (it will wipe this database for each test run)::

    $ export NEO4J_BOLT_URL=bolt://neo4j:neo4j@localhost:7687 # (the default)

Setup a virtual environment, install neomodel for development and run the test suite::

    $ virtualenv venv
    $ source venv/bin/activate
    $ python setup.py develop
    $ pytest

If your running a neo4j database for the first time the test suite will set the password to 'test'.

If you have ``docker-compose`` installed, you can run the test suite against all supported Python
interpreters and neo4j versions::

    # in the project's root folder:
    $ ./tests-with-docker-compose.sh


.. image:: https://badges.gitter.im/Join%20Chat.svg
   :alt: Join the chat at https://gitter.im/neo4j-contrib/neomodel
   :target: https://gitter.im/neo4j-contrib/neomodel?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge
