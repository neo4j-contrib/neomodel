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

Documentation
=============

Available on readthedocs_.

.. _readthedocs: http://neomodel.readthedocs.org

Requirements
============

- Python 2.7, 3.4
- neo4j 2.0, 2.1, 2.2

Installation
============

Install from pypi (recommended)::

    $ pip install neomodel

To install from github::

    $ pip install git+git://github.com/robinedwards/neomodel.git@HEAD#egg=neomodel-dev

Authentication
--------------
Please note that if you are utilizing Neo4j version 2.2 or newer there are
some additional setup steps necessary relating to authentication. As of version 2.2
Neo4j authentication is activated by default on new instances. Please follow the
outstanding documentation provided by py2neo's Authentication_
section to setup new credentials. If you are utilizing a hosted service this
is most likely already taken care for you.

.. _Authentication: http://py2neo.org/2.0/essentials.html#authentication

Upgrading 1.x to 2.x
====================
There is one modification that is necessary when transitioning from version
1.x to 2.x relating to direct cypher queries. In version 1.x performing a
cypher query always returned at least one array within an array. This enabled
some assumptions to be made when querying for single object directly.
Since you could assume the result would always be a list within a list
the result of a response could be safely accessed like the following::

    query = 'MATCH (a:Profile {username: "%s"}) RETURN a' % (username)
    res, col = db.cypher_query(query)
    end_result = res[0][0]

If there wasn't a Profile with the given username nothing would fail out and
``end_result`` would be set to an empty list.

In version 2.x we lean a bit more on py2neo to handle the response. This results
in what py2neo refers to as a RecordList_.
A RecordList is a list of Record_ objects which provide
a few more capabilities on accessing the results. The draw back is
that now accessing the above query at ``res[0][0]`` will result in an ``IndexError``
due to the new response being an empty ``RecordList``. Py2neo has however provided
a solution to this which is the one_ method. This method can be called on the
cypher query response to achieve the old ``res[0][0]`` functionality. So in
version 2 the above query would look like::

    query = 'MATCH (a:Profile {username: "%s"}) RETURN a' % (username)
    res, col = db.cypher_query(query)
    end_result = res.one()

This will result in ``end_result`` being set to ``None``.

.. _RecordList: http://py2neo.org/2.0/cypher.html#py2neo.cypher.RecordList
.. _Record: http://py2neo.org/2.0/cypher.html#py2neo.cypher.Record
.. _one: http://py2neo.org/2.0/cypher.html#py2neo.cypher.RecordList.one

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


.. image:: https://badges.gitter.im/Join%20Chat.svg
   :alt: Join the chat at https://gitter.im/robinedwards/neomodel
   :target: https://gitter.im/robinedwards/neomodel?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge
