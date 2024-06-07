.. _spatial_properties:

==================
Spatial Properties
==================

The Point
=========

Starting with version 3.4.0, Neo4j supports `datatypes that enable geospatial operations
<https://medium.com/neo4j/whats-new-in-neo4j-spatial-features-586d69cda8d0>`_ and specifically, the most fundamental
of those, the `Point <https://neo4j.com/docs/developer-manual/3.4/cypher/syntax/spatial/>`_.

`Points`, in general, are defined over a `Spatial Reference System
<https://en.wikipedia.org/wiki/Spatial_reference_system>`_ (a.k.a Coordinate Reference System (CRS)), that describes the
'shape' of the space that a `Point` is part of.

At the time of writing [#f1]_, Neo4j supports two broad families of CRSs, the `Cartesian
<https://en.wikipedia.org/wiki/Cartesian_coordinate_system>`_ and the `World Geodesic
System WGS84 <https://en.wikipedia.org/wiki/World_Geodetic_System#WGS84>`_. Without any further specification,
Cartesian Points lie on a 'flat' space that extends to infinity in all dimensions while geodesic points are generally
assumed to lie on the surface of an ellipsoid (e.g: the surface of a planet) and 'WGS-84' points specifically, are
assumed to lie on a particular ellipsoid that is used to reference **any** point on Earth.

Cartesian and Geographical points can have two or three dimensions which are referenced with different names, depending
on the Point's type. Therefore:

* Cartesian points have **x,y[, z]** coordinates
* Geographcal points have **longitude, latitude[, height]** coordinates.

Where **[]** denotes a possible third dimension if required.


Points in Neo4j
===============

Point properties use the `point(.) <https://neo4j.com/docs/developer-manual/current/cypher/functions/spatial/>`_
keyword, where **.** denotes a mapping that describes the properties of the point.

For example, to create a node with ``SomeLabel`` and a ``location`` property, the following query can be used::

    CREATE (a:SomeLabel{location:point({x:0.0,y:0.0})});

And if the CRS needs to be specified explicitly, then::

    CREATE (a:SomeLabel{location:point({x:0,y:0, crs:'cartesian'})});


Points in `neomodel`
====================

``neomodel`` provides two data types for the marshalling and validation of ``Point`` datatypes. These are:

1. :class:`~neomodel.contrib.spatial_properties.NeomodelPoint`
    * Provides the ``Point`` data type.

2. :class:`~neomodel.contrib.spatial_properties.PointProperty`
    * Provides the marshalling and data validation for the ``Point`` dat type.

Since ``NeomodelPoint`` depends on a Python package called ``shapely`` (more on this in the next section), if ``shapely``
is not found in the system, any attempt to import anything from `neomodel.contrib.spatial_properties` will raise
an exception.


`NeomodelPoint` in detail
=========================

In most cases, a higher level application that is making use of ``neomodel`` to access its data in the backend is likely
to require to have these points participate in more complex geospatial (or geometric) operations. For example, answer
questions such as 'Is a point within a specific boundary?', 'What is the shortest distance to a particular Point' and
others.

For this reason, a :class:`~neomodel.contrib.spatial_properties.NeomodelPoint` is basically a `shapely.geometry.Point
<http://toblerity.org/shapely/manual.html#geometric-objects>`_, meaning that ``Point`` s to and from the database can
participate directly to all operations supported by ``shapely`` or further geospatial processing via `PySAL
<https://pysal.readthedocs.io/en/latest/users/tutorials/shapely.html>`_.

Just like ``shapely.geometry.Point``, ``NeomodelPoint`` s are **immutable**. This means that once they are instantiated,
their value (whether ``x, y[, z]`` or ``longitude, latitude[, height]``) **cannot** be changed.

In contrast to ``shapely.geometry.Point`` however, a :class:`~neomodel.contrib.spatial_properties.NeomodelPoint` also
**requires** its ``crs`` to be defined for validation purposes.


`PointProperty` in detail
=========================

``PointProperty`` represents a Node or Relationship property in ``neomodel`` and provides validation and datatype
marshalling for it.

``PointProperty`` properties support exactly the same broad features that are expected of a ``neomodel`` property, such as:

1. Participation in indices (via ``index=True`` or ``unique_index=True``)
2. Default values (via ``default=neomodel.contrib.spatial_properties.NeomodelPoint(...)`` or a callable that must return
   a ``NeomodelPoint``.
3. Participation of ``NeomodelPoint`` in elements of ``ArrayProperty`` (via the ``base_property`` keyword of
   :class:`~neomodel.properties.ArrayProperty`)

But more importantly, during their definition, ``PointProperty`` properties **require their `crs` to be set**. If a
``PointProperty`` instantiation does not involve its ``crs``, an exception will be raised.


Examples
========

Working with `NeomodelPoint`
----------------------------

``NeomodelPoint`` has a copy constructor which allows it to be instantiated either via a ``shapely.geometry.Point`` or
via a ``NeomodelPoint``. In the case of ``NeomodelPoint``, the use of the copy constructor is straightforward: ::

    new_object = neomodel.contrib.spatial_properties.NeomodelPoint(old_object);

Where ``old_object`` is also a ``NeomodelPoint``. In this case, ``new_object`` will have exactly the same coordinates **and**
CRS as ``old_object``.

When copying ``shapely`` points however, it is necessary to define the ``crs`` via a keyword by the same name: ::

    new_object = neomodel.contrib.spatial_properties.NeomodelPoint(shapely.geometry.Point((0.0,0.0)), crs='cartesian');

As a general rule, if ``crs`` is not defined during the construction of a ``NeomodelPoint``, the constructor will try to
infer what sort of point is attempted to be created or raise an exception if that is impossible. As a rule of thumb,
*always define the `crs` the points are expected to be expressed in*.

`NeomodelPoint`s can be constructed just like `shapely` points do, via a simple tuple of `float` values with a length
of 2 or 3: ::

    new_object = neomodel.contrib.spatial_properties.NeomodelPoint((0.0,0.0))

This call will create a ``crs='cartesian'`` point. If the tuple was of length three and the ``crs`` was not specified, it
would be inferred as ``crs='cartesian-3d'``.

The distinction between geometric and geographical points is enforced by ``NeomodelPoint`` by providing separate
accessors / keyword parameters for each point type. For example: 

This call will create a `cartesian-3d` point: ::

    new_object = neomodel.contrib.spatial_properties.NeomodelPoint(x=0.0, y=0.0, z=12.0)

But this call will raise an exception, because geographical points **do not have x,y,z components**: ::

    new_object = neomodel.contrib.spatial_properties.NeomodelPoint(x=0.0, y=0.0, z=12.0, crs='wgs-84-3d')

Similarly, the following is valid: ::

    new_object = neomodel.contrib.spatial_properties.NeomodelPoint(x=0.0, y=0.0, z=12.0)
    print("The x component of new_object equals {}`.format(new_object.x))

But this will fail: ::

    new_object = neomodel.contrib.spatial_properties.NeomodelPoint(x=0.0, y=0.0, z=12.0) #A cartesian-3d point
    print("The longitude component of new_object equals {}`.format(new_object.longitude))

Because points defined over a Cartesian CRS, **do not have longitude, latitude, height components** (and vice versa).

Working with `PointProperty`
----------------------------
To define a ``PointProperty`` Node property, simply specify it along with its ``crs``: ::

    class SomeEntity(neomodel.StructuredNode):
        entity_id = neomodel.UniqueIdProperty()
        location = neomodel.PointProperty(crs='wgs-84')

Given this definition of ``SomeEntity``, an object can be created by: ::

    my_entity = SomeEntity(location=neomodel.contrib.spatial_properties.NeomodelPoint((0.0,0.0), crs='wgs-84')).save()

In the above call, setting the ``crs`` of the ``NeomodelPoint`` passed as the ``location`` property of ``SomeEntity`` to any
other value than the ``crs`` that was defined in the definition of ``PointProperty`` would result in an exception.

Continuing from the above example, to *update* the value of `location` would require: ::

    my_entity.location=neomodel.contrib.spatial_properties.NeomodelPoint((4.0,4.0), crs='wgs-84'))
    my_entity.save()

.. [#f1] Novemeber 2018
