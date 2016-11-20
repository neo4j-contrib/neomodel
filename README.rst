.. image:: https://raw.githubusercontent.com/robinedwards/neomodel/master/doc/source/_static/neomodel-300.png
   :alt: neomodel

An Object Graph Mapper (OGM) for the neo4j_ graph database, built on the awesome neo4j_driver_

- Familiar Django model style definitions.
- Powerful query API.
- Enforce your schema through cardinality restrictions.
- Full transaction support.
- Thread safe.
- Hooks including (optional) Django signals support.

.. _neo4j: https://www.neo4j.org
.. _neo4j_driver: https://github.com/neo4j/neo4j-python-driver

.. image:: https://secure.travis-ci.org/robinedwards/neomodel.png
    :target: https://secure.travis-ci.org/robinedwards/neomodel/

Documentation
=============

Available on readthedocs_.

.. _readthedocs: http://neomodel.readthedocs.org

Requirements
============

- Python 2.7, 3.5
- neo4j 3+

Installation
============

Install from pypi (recommended)::

    $ pip install neomodel

To install from github::

    $ pip install git+git://github.com/robinedwards/neomodel.git@HEAD#egg=neomodel-dev

Upgrading 2.x to 3.x
====================

 * Now utilises neo4j_driver as the backend which uses bolt so neo4j 3 is required
 * NEO4J_REST_URL has become NEO4J_BOLT_URL (see docs below)
 * The deprecated category() method on StructuredNode has been removed
 * The streaming=True flag is now irrelevant with bolt and produces a deprecation warning
 * Batch operations must now be wrapped in a transaction in order to be atomic.

Contributing
============

Ideas, bugs, tests and pull requests always welcome.

Running the test suite
----------------------

Make sure you have a fresh virtualenv and `nose` installed::

    $ pip install nose

A Neo4j database to run the tests on, make sure you have set a password from the web interface prior to running the tests. (it will wipe this database)::

    $ export NEO4J_BOLT_URL=bolt://neo4j:test@localhost # (the default)

Setup a virtual environment, install neomodel for development and run the test suite::

    $ virtualenv venv
    $ source venv/bin/activate
    $ python setup.py develop
    $ nosetests -s


.. image:: https://badges.gitter.im/Join%20Chat.svg
   :alt: Join the chat at https://gitter.im/robinedwards/neomodel
   :target: https://gitter.im/robinedwards/neomodel?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge
