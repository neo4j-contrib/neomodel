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

.. image:: https://readthedocs.org/projects/neomodel/badge/?version=latest
    :alt: Documentation Status
    :scale: 100%
    :target: https://neomodel.readthedocs.io/en/latest/?badge=latest

Maintenance notice
==================

This project didn't receive releases between December 2021 and early 2023. Active maintenance of the project is now being picked up again.
Please look at the Issues page, and especially this thread for more information about the current plan : https://github.com/neo4j-contrib/neomodel/issues/653

Documentation
=============

(Needs an update, but) Available on readthedocs_.

.. _readthedocs: http://neomodel.readthedocs.org

Requirements
============

- Python 3.7+
- neo4j 3.5 and all 4.x versions (up to 4.4) - Neo4j Python Driver 4.1 https://neo4j.com/docs/api/python-driver/4.4/

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

If you are running a neo4j database for the first time the test suite will set the password to 'test'.
If the database is already populated, the test suite will abort with an error message and ask you to re-run it with the
``--resetdb`` switch. This is a safeguard to ensure that the test suite does not accidentally wipe out a database if you happen 
to not have restarted your Neo4j server to point to a (usually named) ``debug.db`` database.

If you have ``docker-compose`` installed, you can run the test suite against all supported Python
interpreters and neo4j versions: ::

    # in the project's root folder:
    $ sh ./tests-with-docker-compose.sh

