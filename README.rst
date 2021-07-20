.. image:: https://raw.githubusercontent.com/neo4j-contrib/neomodel/master/doc/source/_static/neomodel-300.png
   :alt: neomodel

An Object Graph Mapper (OGM) for the neo4j_ graph database, built on the awesome neo4j_driver_

- Familiar class based model definitions with proper inheritance.
- Powerful query API.
- Schema enforcement through cardinality restrictions.
- Full transaction support.
- Thread safe.
- Pre/post save/delete hooks.
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

(Needs an update, but) Available on readthedocs_.

.. _readthedocs: http://neomodel.readthedocs.org

Requirements
============

- Python 3.5+ - Neo4j Python Driver 4.3 https://neo4j.com/docs/api/python-driver/current/
- neo4j 3.5, 4.0, 4.1 (4.3 currently being tested) - Neo4j Python Driver 4.1 https://neo4j.com/docs/api/python-driver/current/

Installation
============

Install from pypi (recommended)::

    $ pip install neomodel ($ source dev # To install all things needed in a Python3 venv)

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

As of release `3.3.2` we now have a curated list of issues / development targets for
`neomodel` available on `the Wiki <https://github.com/neo4j-contrib/neomodel/wiki/TODOs-&-Enhancements>`_.

If you are interested in developing `neomodel` further, pick a subject from the list and open a Pull Request (PR) for 
it. If you are adding a feature that is not captured in that list yet, consider if the work for it could also 
contribute towards delivering any of the existing todo items too.

Running the test suite
----------------------

Make sure you have a Neo4j database version 3 or higher to run the tests on.::

    $ export NEO4J_BOLT_URL=bolt://<username>:<password>@localhost:7687 # check your username and password

Ensure `dbms.security.auth_enabled=true` in your database configuration file.
Setup a virtual environment, install neomodel for development and run the test suite::

    $ source dev
    $ pytest

If you are running a neo4j database for the first time the test suite will set the password to 'test'.
If the database is already populated, the test suite will abort with an error message and ask you to re-run it with the
`--resetdb` switch. This is a safeguard to ensure that the test suite does not accidentally wipe out a database if you happen to not have restarted your Neo4j server to point to a (usually named) `debug.db` database.

If you have ``docker-compose`` installed, you can run the test suite against all supported Python
interpreters and neo4j versions::

    # in the project's root folder:
    $ ./tests-with-docker-compose.sh


.. image:: https://badges.gitter.im/Join%20Chat.svg
   :alt: Join the chat at https://gitter.im/neo4j-contrib/neomodel
   :target: https://gitter.im/neo4j-contrib/neomodel?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge
