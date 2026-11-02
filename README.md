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

**For neomodel releases 6.x :**

- Python 3.10+
- Neo4j 2025.x.x, 5.x, 4.4 (LTS)
- Neo4j Enterprise, Community and Aura are supported

**For neomodel releases 5.x :**

-   Python 3.8+
-   Neo4j 5.x, 4.4 (LTS)

**For neomodel releases 4.x :**

-   Python 3.7 -\> 3.10
-   Neo4j 4.x (including 4.4 LTS for neomodel version 4.0.10)

# Documentation

Available on
[readthedocs](http://neomodel.readthedocs.org).

Also check out DeepWiki : [![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/neo4j-contrib/neomodel)

# New in 7.0.0

* **Full typing support**: `NodeSet` is now generic over its node class and instance properties resolve to their Python values, so `MyNode.nodes.get()` and `node.some_property` are correctly typed in IDEs and type checkers. The package type-checks cleanly under mypy, enforced in CI.
* **Django-style bulk operations** on the node set: `MyNode.nodes.bulk_create()`, `bulk_create_or_update()`, `bulk_get_or_create()` and `bulk_save()`, each running in one or two round-trips instead of one per node.
* **Mutually exclusive relationships** via an `exclusion_group` parameter on `RelationshipTo`/`RelationshipFrom`.
* **Array membership filters** `includes`/`includes_all`/`includes_any` for `ArrayProperty`, usable in `filter()` and `match()`.
* **Optional Pydantic bridge** (`neomodel.contrib.pydantic`, install with `neomodel[pydantic]`) to generate Pydantic v2 models from node classes and convert between them.
* **Lazy node-class discovery**: classes are resolved from the live hierarchy instead of a global registry, so hot-reload (dev servers, Streamlit) always works and `config.allow_reload` is no longer needed.

### Breaking changes

* `RelationshipManager.match()` (and `Traversal.match()`) now returns a `NodeSet`, exposing the full NodeSet API (`get`/`first`/`filter`/`order_by`/...), instead of a `Traversal`.
* `config.DATABASE_URL` no longer defaults to `bolt://neo4j:foobarbaz@localhost:7687`. A connection must now be configured explicitly, or running a query raises a clear error.
* See more breaking changes in the [documentation](http://neomodel.readthedocs.org)

# Installation

Install from pypi (recommended):

    $ pip install neomodel ($ source dev # To install all things needed in a Python3 venv)

    # neomodel can use the Rust extension to the Neo4j driver for faster transport, to install use:

    $ pip install neomodel[rust-driver-ext]

    # neomodel has some optional dependencies (Shapely, pandas, numpy), to install these use:

    $ pip install neomodel[extras, rust-driver-ext]

To install from github:

    $ pip install git+git://github.com/neo4j-contrib/neomodel.git@HEAD#egg=neomodel-dev

# Performance comparison

You can find some performance tests made using Locust [in this repo](https://github.com/mariusconjeaud/neomodel-locust).

Two learnings from this :

* The wrapping of the driver made by neomodel is very thin performance-wise : it does not add a lot of overhead ;
* When used in a concurrent fashion, async neomodel is faster than concurrent sync neomodel, and a lot faster than serial queries.

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

    $ pip install -r requirements-dev.txt
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

## Developing with async

### Transpiling async -> sync

We use [this great library](https://github.com/python-trio/unasync) to automatically transpile async code into its sync version.

In other words, when contributing to neomodel, only update the `async` code in `neomodel/async_`, then run : :

    bin/make-unasync
    isort .
    black .

Note that you can also use the pre-commit hooks for this.

### Specific async/sync code
This transpiling script mainly does two things :

- It removes the await keywords, and the Async prefixes in class names
- It does some specific replacements, like `adb`->`db`, `mark_async_test`->`mark_sync_test`

It might be that your code should only be run for `async`, or `sync` ; or you want different stubs to be run for `async` vs `sync`.
You can use the following utility function for this - taken from the official [Neo4j python driver code](https://github.com/neo4j/neo4j-python-driver) :

    # neomodel/async_/core.py
    from neomodel._async_compat.util import AsyncUtil

    # AsyncUtil.is_async_code is always True
    if AsyncUtil.is_async_code:
        # Specific async code
        # This one gets run when in async mode
        assert await Coffee.nodes.check_contains(2)
    else:
        # Specific sync code
        # This one gest run when in sync mode
        assert 2 in Coffee.nodes

You can check [test_match_api](test/async_/test_match_api.py) for some good examples, and how it's transpiled into sync.

