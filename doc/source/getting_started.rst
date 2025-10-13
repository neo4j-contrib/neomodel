===============
Getting started
===============

Connecting
==========

Before executing any neomodel code, set the connection url::

    from neomodel import get_config
    
    config = get_config()
    config.database_url = 'bolt://neo4j:password@localhost:7687'  # default

This must be called early on in your app, if you are using Django the `settings.py` file is ideal.

See the Configuration page (:ref:`_configuration_options_doc`) for config options.

If you are using your neo4j server for the first time you will need to change the default password.
This can be achieved by visiting the neo4j admin panel (default: ``http://localhost:7474`` ).

Querying the graph
==================

neomodel is mainly used as an OGM (see next section), but you can also use it for direct Cypher queries : ::

    from neomodel import db
    results, meta = db.cypher_query("RETURN 'Hello World' as message")


Defining Node Entities and Relationships
========================================

Below is a definition of three related nodes `Person`, `City` and `Country`: ::

    from neomodel import (get_config, StructuredNode, StringProperty, IntegerProperty,
        UniqueIdProperty, RelationshipTo)


    config = get_config()
    config.database_url = 'bolt://neo4j_username:neo4j_password@localhost:7687'

    class Country(StructuredNode):
        code = StringProperty(unique_index=True, required=True)

    class City(StructuredNode):
        name = StringProperty(required=True)
        country = RelationshipTo(Country, 'FROM_COUNTRY')

    class Person(StructuredNode):
        uid = UniqueIdProperty()
        name = StringProperty(unique_index=True)
        age = IntegerProperty(index=True, default=0)

        # traverse outgoing IS_FROM relations, inflate to Country objects
        country = RelationshipTo(Country, 'IS_FROM')

        # traverse outgoing LIVES_IN relations, inflate to City objects
        city = RelationshipTo(City, 'LIVES_IN')

Nodes are defined in the same way classes are defined in Python with the only difference that data members of those
classes that are intended to be stored to the database must be defined as ``neomodel`` property objects. For more
detailed information on property objects please see the section on :ref:`property_types`.

**If** you have a need to attach "ad-hoc" properties to nodes that have not been specified at its definition, then 
consider deriving from the :ref:`semistructurednode_doc` class.

Relationships are defined via ``Relationship, RelationshipTo, RelationshipFrom`` objects. ``RelationshipTo,
RelationshipFrom`` can also specify the direction that a relationship would be allowed to be traversed. In this
particular example, ``Country`` objects would be accessible by ``Person`` objects but not the other way around.

When the relationship can be bi-directional, please avoid establishing two complementary ``RelationshipTo,
RelationshipFrom`` relationships and use ``Relationship``, on one of the class definitions instead. In all of these
cases, navigability matters more to the model as defined in Python. A relationship will be established in Neo4J but
in the case of ``Relationship`` it will be possible to be queried in either direction.

Neomodel automatically creates a label for each ``StructuredNode`` class in the database with the corresponding indexes
and constraints.

.. _inspect_database_doc:

Database Inspection - Requires APOC
===================================
You can inspect an existing Neo4j database to generate a neomodel definition file using the ``inspect`` command::

    $ neomodel_inspect_database --db bolt://neo4j_username:neo4j_password@localhost:7687 --write-to yourapp/models.py

This will generate a file called ``models.py`` in the ``yourapp`` directory. This file can be used as a starting point,
and will contain the necessary module imports, as well as class definition for nodes and, if relevant, relationships.

Ommitting the ``--db`` argument will default to the ``NEO4J_BOLT_URL`` environment variable. This is useful for masking
your credentials.

Note that you can also print the output to the console instead of writing a file by omitting the ``--write-to`` option.

If you have a database with a large number of nodes and relationships,
this script can take a long time to run (during our tests, it took 30 seconds for 500k nodes and 1.3M relationships).
You can speed it up by not scanning for relationship properties and/or relationship cardinality, using these options :
``--no-rel-props`` and ``--no-rel-cardinality``.
Note that this will still add relationship definition to your nodes, but without relationship models ;
and cardinality will be default (ZeroOrMore).

.. note::

    This command will only generate the definition for nodes and relationships that are present in the
    database. If you want to generate a complete definition file, you will need to add the missing classes manually.

    Also, this has only been tested with single-label nodes. If you have multi-label nodes, you will need to double check,
    and add the missing labels manually in the relevant way.

    Finally, relationship cardinality is guessed from the database by looking at existing relationships, so it might
    guess wrong on edge cases.

.. note:: 

    The script relies on the method apoc.meta.cypher.types to parse property types. So APOC must be installed on your Neo4j server
    for this script to work.

Applying constraints and indexes
================================
After creating a model in Python, any constraints or indexes must be applied to Neo4j and ``neomodel`` provides a
script (:ref:`neomodel_install_labels`) to automate this: ::

    $ neomodel_install_labels yourapp.py someapp.models --db bolt://neo4j_username:neo4j_password@localhost:7687

It is important to execute this after altering the schema and observe the number of classes it reports.

Ommitting the ``--db`` argument will default to the ``NEO4J_BOLT_URL`` environment variable. This is useful for masking
your credentials.

Remove existing constraints and indexes
=======================================
Similarly, ``neomodel`` provides a script (:ref:`neomodel_remove_labels`) to automate the removal of all existing constraints and indexes from
the database, when this is required: ::

    $ neomodel_remove_labels --db bolt://neo4j_username:neo4j_password@localhost:7687

After executing, it will print all indexes and constraints it has removed.

Ommitting the ``--db`` argument will default to the ``NEO4J_BOLT_URL`` environment variable. This is useful for masking
your credentials.

Generate class diagram
======================
You can generate a class diagram of your models using the ``neomodel_generate_diagram`` command::

    $ neomodel_generate_diagram models/my_models.py --file-type arrows --write-to-dir img

You must specify a directory in which to lookup neomodel classes (nodes and rels). Typing '.' will search in your whole directory.

You have the option to generate the diagram in different file types using ``--file-type`` : ``arrows``, ``puml`` (which uses the dot notation).

Ommitting the ``--write-to-dir`` option will default to the current directory.

.. note::

    Property types and the presence of indexes, constraints and required rules will be displayed on the nodes.
    
    Relationship properties are not supported in the diagram generation.

Create, Update, Delete operations
=================================

Using convenience methods such as::

    jim = Person(name='Jim', age=3).save() # Create
    jim.age = 4
    jim.save() # Update, (with validation)
    jim.delete()
    jim.refresh() # reload properties from the database
    jim.element_id # neo4j internal element id

Retrieving nodes
================

Using the ``.nodes`` class property::

    # Return all nodes
    all_nodes = Person.nodes.all()

    # Returns Person by Person.name=='Jim' or raises neomodel.DoesNotExist if no match
    jim = Person.nodes.get(name='Jim')


``.nodes.all()`` and ``.nodes.get()`` can also accept a ``lazy=True`` parameter which will result in those functions
simply returning the node IDs rather than every attribute associated with that Node. ::

    # Will return None unless "bob" exists
    someone = Person.nodes.get_or_none(name='bob')

    # Will return the first Person node with the name bob. This raises neomodel.DoesNotExist if there's no match.
    someone = Person.nodes.first(name='bob')

    # Will return the first Person node with the name bob or None if there's no match
    someone = Person.nodes.first_or_none(name='bob')

    # Return set of nodes
    people = Person.nodes.filter(age__gt=3)

Iteration, slicing and more
---------------------------

Iteration, slicing and counting is also supported::

    # Iterable
    for coffee in Coffee.nodes:
        print coffee.name

    # Sliceable using python slice syntax
    coffee = Coffee.nodes.filter(price__gt=2)[2:]

The slice syntax returns a NodeSet object which can in turn be chained.

Length and boolean methods do not return NodeSet objects and cannot be chained further::

    # Count with __len__
    print len(Coffee.nodes.filter(price__gt=2))

    if Coffee.nodes:
        print "We have coffee nodes!"

Relationships
=============

Working with relationships::

    germany = Country(code='DE').save()
    jim.country.connect(germany)
    berlin = City(name='Berlin').save()
    berlin.country.connect(germany)
    jim.city.connect(berlin)

    if jim.country.is_connected(germany):
        print("Jim's from Germany")

    for p in germany.inhabitant.all():
        print(p.name) # Jim

    len(germany.inhabitant) # 1

    # Find people called 'Jim' in germany
    germany.inhabitant.filter(name='Jim')

    # Find all the people called in germany except 'Jim'
    germany.inhabitant.exclude(name='Jim')

    # Remove Jim's country relationship with Germany
    jim.country.disconnect(germany)

    usa = Country(code='US').save()
    jim.country.connect(usa)
    jim.country.connect(germany)

    # Remove all of Jim's country relationships
    jim.country.disconnect_all()

    jim.country.connect(usa)
    # Replace Jim's country relationship with a new one
    jim.country.replace(germany)


Retrieving additional relations
===============================

.. note::

   You can fetch one or more relations within the same call
   to `.traverse()` and you can mix optional and non-optional
   relations, like::

    Person.nodes.traverse('city__country', Path(value='country', optional=True)).all()

.. note::

   If your path looks like ``(startNode:Person)-[r1]->(middleNode:City)<-[r2]-(endNode:Country)``,
   then you will get a list of results, where each result is a list of ``(startNode, r1, middleNode, r2, endNode)``.
   These will be resolved by neomodel, so ``startNode`` will be a ``Person`` class as defined in neomodel for example.


Async neomodel
==============

neomodel supports asynchronous operations using the async support of neo4j driver. The examples below take a few of the above examples,
but rewritten for async::

    from neomodel import adb
    results, meta = await adb.cypher_query("RETURN 'Hello World' as message")

OGM with async ::

    # Note that properties do not change, but nodes and relationships now have an Async prefix
    from neomodel import (AsyncStructuredNode, StringProperty, IntegerProperty,
        UniqueIdProperty, AsyncRelationshipTo)

    class Country(AsyncStructuredNode):
        code = StringProperty(unique_index=True, required=True)

    class City(AsyncStructuredNode):
        name = StringProperty(required=True)
        country = AsyncRelationshipTo(Country, 'FROM_COUNTRY')

    # Operations that interact with the database are now async
    # Return all nodes
    # Note that the nodes object is awaitable as is
    all_nodes = await Country.nodes

    # Relationships
    germany = await Country(code='DE').save()
    await jim.country.connect(germany)

Most _dunder_ methods for nodes and relationships had to be overriden to support async operations. The following methods are supported ::

    # Examples below are taken from the various tests. Please check them for more examples.
    # Length
    dogs_bonanza = await Dog.nodes.get_len()
    # Sync equivalent - __len__
    dogs_bonanza = len(Dog.nodes)
    # Note that len(Dog.nodes) is more efficient than Dog.nodes.__len__

    # Existence
    assert not await Customer.nodes.filter(email="jim7@aol.com").check_bool()
    # Sync equivalent - __bool__
    assert not Customer.nodes.filter(email="jim7@aol.com")
    # Also works for check_nonzero => __nonzero__

    # Contains
    assert await Coffee.nodes.check_contains(aCoffeeNode)
    # Sync equivalent - __contains__
    assert aCoffeeNode in Coffee.nodes

    # Get item
    assert len(list((await Coffee.nodes)[1:])) == 2
    # Sync equivalent - __getitem__
    assert len(list(Coffee.nodes[1:])) == 2


Full example
============

The example below will show you how you can mix and match query operations, as described in :ref:`Filtering and ordering`, :ref:`Path traversal`, or :ref:`Advanced query operations`::

    # These are the class definitions used for the query below
    class HasCourseRel(AsyncStructuredRel):
        level = StringProperty()
        start_date = DateTimeProperty()
        end_date = DateTimeProperty()


    class Course(AsyncStructuredNode):
        name = StringProperty()


    class Building(AsyncStructuredNode):
        name = StringProperty()


    class Student(AsyncStructuredNode):
        name = StringProperty()

        parents = AsyncRelationshipTo("Student", "HAS_PARENT", model=AsyncStructuredRel)
        children = AsyncRelationshipFrom("Student", "HAS_PARENT", model=AsyncStructuredRel)
        lives_in = AsyncRelationshipTo(Building, "LIVES_IN", model=AsyncStructuredRel)
        courses = AsyncRelationshipTo(Course, "HAS_COURSE", model=HasCourseRel)
        preferred_course = AsyncRelationshipTo(
            Course,
            "HAS_PREFERRED_COURSE",
            model=AsyncStructuredRel,
            cardinality=AsyncZeroOrOne,
        )

    # This is the query
    full_nodeset = (
        await Student.nodes.filter(name__istartswith="m", lives_in__name="Eiffel Tower") # Combine filters
        .order_by("name")
        .traverse(
            "parents",
            Path(value="children__preferred_course", optional=True)
        ) # Combine traversals
        .subquery(
            Student.nodes.traverse("courses") # Root variable student will be auto-injected here
            .intermediate_transform(
                {"rel": RelationNameResolver("courses")},
                ordering=[
                    RawCypher("toInteger(split(rel.level, '.')[0])"),
                    RawCypher("toInteger(split(rel.level, '.')[1])"),
                    "rel.end_date",
                    "rel.start_date",
                ], # Intermediate ordering
            )
            .annotate(
                latest_course=Last(Collect("rel")),
            ),
            ["latest_course"],
        )
    )

    # Using async, we need to do 2 await
    # One is for subquery, the other is for resolve_subgraph
    # It only runs a single Cypher query though
    subgraph = await full_nodeset.annotate(
        children=Collect(NodeNameResolver("children"), distinct=True),
        children_preferred_course=Collect(
            NodeNameResolver("children__preferred_course"), distinct=True
        ),
    ).resolve_subgraph()

    # The generated Cypher query looks like this
    query = """
    MATCH (student:Student)-[r1:`HAS_PARENT`]->(student_parents:Student)
    MATCH (student)-[r4:`LIVES_IN`]->(building_lives_in:Building)
    OPTIONAL MATCH (student)<-[r2:`HAS_PARENT`]-(student_children:Student)-[r3:`HAS_PREFERRED_COURSE`]->(course_children__preferred_course:Course)
    WITH *
    # building_lives_in_name_1 = "Eiffel Tower"
    # student_name_1 = "(?i)m.*"
    WHERE building_lives_in.name = $building_lives_in_name_1 AND student.name =~ $student_name_1
    CALL {
        WITH student
        MATCH (student)-[r1:`HAS_COURSE`]->(course_courses:Course)
        WITH r1 AS rel
        ORDER BY toInteger(split(rel.level, '.')[0]),toInteger(split(rel.level, '.')[1]),rel.end_date,rel.start_date
        RETURN last(collect(rel)) AS latest_course
    }
    RETURN latest_course, student, student_parents, r1, student_children, r2, course_children__preferred_course, r3, building_lives_in, r4, collect(DISTINCT student_children) AS children, collect(DISTINCT course_children__preferred_course) AS children_preferred_course
    ORDER BY student.name
    """