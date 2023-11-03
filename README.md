![neomodel](https://raw.githubusercontent.com/neo4j-contrib/neomodel/master/doc/source/_static/neomodel-300.png)

An Object Graph Mapper (OGM) for the [neo4j](https://neo4j.com/) graph
database, built on the awesome
[neo4j_driver](https://github.com/neo4j/neo4j-python-driver)

If you need assistance with neomodel, please create an issue on the
GitHub repo found at <https://github.com/neo4j-contrib/neomodel/>.

-   Familiar class based model definitions with proper inheritance.
-   Powerful query API.
-   Schema enforcement through cardinality restrictions.
-   Full transaction support.
-   Thread safe.
-   Pre/post save/delete hooks.
-   Django integration via
    [django_neomodel](https://github.com/neo4j-contrib/django-neomodel)

[![Reliability Rating](https://sonarcloud.io/api/project_badges/measure?project=neo4j-contrib_neomodel&metric=reliability_rating)](https://sonarcloud.io/summary/new_code?id=neo4j-contrib_neomodel)
[![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=neo4j-contrib_neomodel&metric=security_rating)](https://sonarcloud.io/summary/new_code?id=neo4j-contrib_neomodel)
[![Documentation Status](https://readthedocs.org/projects/neomodel/badge/?version=latest)](https://neomodel.readthedocs.io/en/latest/?badge=latest)

# Requirements

**For neomodel releases 5.x :**

-   Python 3.7+
-   Neo4j 5.x, 4.4 (LTS)

**For neomodel releases 4.x :**

-   Python 3.7 -\> 3.10
-   Neo4j 4.x (including 4.4 LTS for neomodel version 4.0.10)

# Documentation

(Needs an update, but) Available on
[readthedocs](http://neomodel.readthedocs.org).

# Upcoming breaking changes notice - \>=5.3

Based on Python version [status](https://devguide.python.org/versions/),
neomodel will be dropping support for Python 3.7 in the next release
(5.3). This does not mean neomodel will stop working on Python 3.7, but
it will no longer be tested against it. Instead, we will try to add
support for Python 3.12.

Another potential breaking change coming up is adding async support to
neomodel. But we do not know when this will happen yet, or if it will
actually be a breaking change. We will definitely push this in a major
release though. More to come on that later.

Finally, we are looking at refactoring some standalone methods into the
Database() class. More to come on that later.

# Installation

Install from pypi (recommended):

    $ pip install neomodel ($ source dev # To install all things needed in a Python3 venv)

    # Neomodel has some optional dependencies (including Shapely), to install these use:

    $ pip install neomodel['extras']

To install from github:

    $ pip install git+git://github.com/neo4j-contrib/neomodel.git@HEAD#egg=neomodel-dev

# Contributing

Ideas, bugs, tests and pull requests always welcome. Please use
GitHub\'s Issues page to track these.

If you are interested in developing `neomodel` further, pick a subject
from the Issues page and open a Pull Request (PR) for it. If you are
adding a feature that is not captured in that list yet, consider if the
work for it could also contribute towards delivering any of the existing
issues too.

## Running the test suite

Make sure you have a Neo4j database version 4 or higher to run the tests
on.:

    $ export NEO4J_BOLT_URL=bolt://<username>:<password>@localhost:7687 # check your username and password

Ensure `dbms.security.auth_enabled=true` in your database configuration
file. Setup a virtual environment, install neomodel for development and
run the test suite: :

    $ pip install -e '.[dev,pandas,numpy]'
    $ pytest

The tests in \"test_connection.py\" will fail locally if you don\'t
specify the following environment variables:

    $ export AURA_TEST_DB_USER=username
    $ export AURA_TEST_DB_PASSWORD=password
    $ export AURA_TEST_DB_HOSTNAME=url

If you are running a neo4j database for the first time the test suite
will set the password to \'test\'. If the database is already populated,
the test suite will abort with an error message and ask you to re-run it
with the `--resetdb` switch. This is a safeguard to ensure that the test
suite does not accidentally wipe out a database if you happen to not
have restarted your Neo4j server to point to a (usually named)
`debug.db` database.

If you have `docker-compose` installed, you can run the test suite
against all supported Python interpreters and neo4j versions: :

    # in the project's root folder:
    $ sh ./tests-with-docker-compose.sh
