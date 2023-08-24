.. image:: https://raw.githubusercontent.com/neo4j-contrib/neomodel/master/doc/source/_static/neomodel-300.png
   :alt: neomodel

An Object Graph Mapper (OGM) for the neo4j_ graph database, built on the awesome neo4j_driver_

If you need assistance with neomodel, please create an issue on the GitHub repo found at https://github.com/neo4j-contrib/neomodel/.

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

.. image:: https://sonarcloud.io/api/project_badges/measure?project=neo4j-contrib_neomodel&metric=reliability_rating
    :alt: Reliability Rating
    :scale: 100%
    :target: https://sonarcloud.io/summary/new_code?id=neo4j-contrib_neomodel

.. image:: https://sonarcloud.io/api/project_badges/measure?project=neo4j-contrib_neomodel&metric=security_rating
    :alt: Security Rating
    :scale: 100%
    :target: https://sonarcloud.io/summary/new_code?id=neo4j-contrib_neomodel

.. image:: https://readthedocs.org/projects/neomodel/badge/?version=latest
    :alt: Documentation Status
    :scale: 100%
    :target: https://neomodel.readthedocs.io/en/latest/?badge=latest

Requirements
============

**For neomodel releases 5.x :**

* Python 3.7+
* Neo4j 5.x, 4.4 (LTS)


**For neomodel releases 4.x :**

* Python 3.7 -> 3.10
* Neo4j 4.x (including 4.4 LTS for neomodel version 4.0.10)


Documentation
=============

(Needs an update, but) Available on readthedocs_.

.. _readthedocs: http://neomodel.readthedocs.org


Upcoming breaking changes notice - >=5.2
========================================

As part of the current quality improvement efforts, we are planning a rework of neomodel's main Database object, which will lead to breaking changes.

The full scope is not drawn out yet, but here are the main points :

* Extracting driver creation and management out of the library => then for operations such as transaction creation, you would need to pass along a driver that you maintain yourself, like below. See issue https://github.com/neo4j-contrib/neomodel/issues/742 for more information, breaking changes, and fixes::

    @db.transaction(driver=my_driver)

* Refactoring standalone methods that depend on the Database singleton into the class itself. See issue https://github.com/neo4j-contrib/neomodel/issues/739
   
We are aiming to release this in neomodel 5.2


Installation
============

Install from pypi (recommended)::

    $ pip install neomodel ($ source dev # To install all things needed in a Python3 venv)

 Neomodel has some optional dependencies (including Shapely), to install these use:

    $ pip install neomodel['extras']

To install from github::

    $ pip install git+git://github.com/neo4j-contrib/neomodel.git@HEAD#egg=neomodel-dev

Contributing
============

Ideas, bugs, tests and pull requests always welcome. Please use GitHub's Issues page to track these.

If you are interested in developing ``neomodel`` further, pick a subject from the Issues page and open a Pull Request (PR) for 
it. If you are adding a feature that is not captured in that list yet, consider if the work for it could also 
contribute towards delivering any of the existing issues too.

Running the test suite
----------------------

Make sure you have a Neo4j database version 4 or higher to run the tests on.::

    $ export NEO4J_BOLT_URL=bolt://<username>:<password>@localhost:7687 # check your username and password

Ensure ``dbms.security.auth_enabled=true`` in your database configuration file.
Setup a virtual environment, install neomodel for development and run the test suite: ::

    $ pip install -e '.[dev]'
    $ pytest

The tests in "test_connection.py" will fail locally if you don't specify the following environment variables::

    $ export AURA_TEST_DB_USER=username
    $ export AURA_TEST_DB_PASSWORD=password
    $ export AURA_TEST_DB_HOSTNAME=url

If you are running a neo4j database for the first time the test suite will set the password to 'test'.
If the database is already populated, the test suite will abort with an error message and ask you to re-run it with the
``--resetdb`` switch. This is a safeguard to ensure that the test suite does not accidentally wipe out a database if you happen 
to not have restarted your Neo4j server to point to a (usually named) ``debug.db`` database.

If you have ``docker-compose`` installed, you can run the test suite against all supported Python
interpreters and neo4j versions: ::

    # in the project's root folder:
    $ sh ./tests-with-docker-compose.sh

