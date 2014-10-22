.. image:: https://raw.githubusercontent.com/robinedwards/neomodel/master/doc/source/_static/neomodel-300.png
   :alt: neomodel

An Object Graph Mapper (OGM) for the neo4j_ graph database, built on the awesome py2neo_.

- Familiar Django model style definitions.
- Powerful query API.
- Enforce your schema through cardinality restrictions.
- Full transaction support.
- Hooks including (optional) Django signals support.

.. _py2neo: http://www.py2neo.org
.. _neo4j: http://www.neo4j.org

.. image:: https://secure.travis-ci.org/robinedwards/neomodel.png
    :target: https://secure.travis-ci.org/robinedwards/neomodel/

.. image:: https://pypip.in/d/neomodel/badge.png
    :target: https://pypi.python.org/pypi/neomodel/
    :alt: Downloads

Documentation
=============

Available on readthedocs_.

.. _readthedocs: http://neomodel.readthedocs.org

Requirements
============

- Python 2.7, 3.4, pypy and pypy3
- neo4j 2.0 or 2.1

Installation
============

Install from pypi (recommended)::

    $ pip install neomodel

To install from github::

    $ pip install git+git://github.com/robinedwards/neomodel.git@HEAD#egg=neomodel-dev

Contributing
============

Ideas, bugs, tests and pull requests always welcome.

Running the test suite
----------------------

Make sure you have a fresh virtualenv and `nose` installed::

    $ pip install nose

A Neo4j database to run the tests on, (it will wipe this database)::

    $ export NEO4J_REST_URL=http://localhost:7474/db/data # (the default)

Install neomodel for development and run the suite::

    $ python setup.py develop
    $ nosetests -s
