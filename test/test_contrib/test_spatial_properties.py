"""
Provides a test case for issue 374 - "Support for Point property type".

For more information please see: https://github.com/neo4j-contrib/neomodel/issues/374
"""

import os
import random

import neo4j.spatial
import pytest

import neomodel
import neomodel.contrib.spatial_properties

from .test_spatial_datatypes import (
    basic_type_assertions,
    check_and_skip_neo4j_least_version,
)


def test_spatial_point_property():
    """
    Tests that specific modes of instantiation fail as expected.

    :return:
    """

    # Neo4j versions lower than 3.4.0 do not support Point. In that case, skip the test.
    check_and_skip_neo4j_least_version(
        340, "This version does not support spatial data types."
    )

    with pytest.raises(ValueError, match=r"Invalid CRS\(None\)"):
        a_point_property = neomodel.contrib.spatial_properties.PointProperty()

    with pytest.raises(ValueError, match=r"Invalid CRS\(crs_isaak\)"):
        a_point_property = neomodel.contrib.spatial_properties.PointProperty(
            crs="crs_isaak"
        )

    with pytest.raises(TypeError, match="Invalid default value"):
        a_point_property = neomodel.contrib.spatial_properties.PointProperty(
            default=(0.0, 0.0), crs="cartesian"
        )


def test_inflate():
    """
    Tests that the marshalling from neo4j to neomodel data types works as expected.

    :return:
    """

    # Neo4j versions lower than 3.4.0 do not support Point. In that case, skip the test.
    check_and_skip_neo4j_least_version(
        340, "This version does not support spatial data types."
    )

    # The test is repeatable enough to try and standardise it. The same test is repeated with the assertions in
    # `basic_type_assertions` and different messages to be able to localise the exception.
    #
    # Array of points to inflate and messages when things go wrong
    values_from_db = [
        (
            neo4j.spatial.CartesianPoint((0.0, 0.0)),
            "Expected Neomodel 2d cartesian point when inflating 2d cartesian neo4j point",
        ),
        (
            neo4j.spatial.CartesianPoint((0.0, 0.0, 0.0)),
            "Expected Neomodel 3d cartesian point when inflating 3d cartesian neo4j point",
        ),
        (
            neo4j.spatial.WGS84Point((0.0, 0.0)),
            "Expected Neomodel 2d geographical point when inflating 2d geographical neo4j point",
        ),
        (
            neo4j.spatial.WGS84Point((0.0, 0.0, 0.0)),
            "Expected Neomodel 3d geographical point inflating 3d geographical neo4j point",
        ),
    ]

    # Run the above tests
    for a_value in values_from_db:
        expected_point = neomodel.contrib.spatial_properties.NeomodelPoint(
            tuple(a_value[0]),
            crs=neomodel.contrib.spatial_properties.SRID_TO_CRS[a_value[0].srid],
        )
        inflated_point = neomodel.contrib.spatial_properties.PointProperty(
            crs=neomodel.contrib.spatial_properties.SRID_TO_CRS[a_value[0].srid]
        ).inflate(a_value[0])
        basic_type_assertions(
            expected_point,
            inflated_point,
            "{}, received {}".format(a_value[1], inflated_point),
        )


def test_deflate():
    """
    Tests that the marshalling from neomodel to neo4j data types works as expected
    :return:
    """
    # Please see inline comments in `test_inflate`. This test function is 90% to that one with very minor differences.
    #

    # Neo4j versions lower than 3.4.0 do not support Point. In that case, skip the test.
    check_and_skip_neo4j_least_version(
        340, "This version does not support spatial data types."
    )

    CRS_TO_SRID = dict(
        [
            (value, key)
            for key, value in neomodel.contrib.spatial_properties.SRID_TO_CRS.items()
        ]
    )
    # Values to construct and expect during deflation
    values_from_neomodel = [
        (
            neomodel.contrib.spatial_properties.NeomodelPoint(
                (0.0, 0.0), crs="cartesian"
            ),
            "Expected Neo4J 2d cartesian point when deflating Neomodel 2d cartesian point",
        ),
        (
            neomodel.contrib.spatial_properties.NeomodelPoint(
                (0.0, 0.0, 0.0), crs="cartesian-3d"
            ),
            "Expected Neo4J 3d cartesian point when deflating Neomodel 3d cartesian point",
        ),
        (
            neomodel.contrib.spatial_properties.NeomodelPoint((0.0, 0.0), crs="wgs-84"),
            "Expected Neo4J 2d geographical point when deflating Neomodel 2d geographical point",
        ),
        (
            neomodel.contrib.spatial_properties.NeomodelPoint(
                (0.0, 0.0, 0.0), crs="wgs-84-3d"
            ),
            "Expected Neo4J 3d geographical point when deflating Neomodel 3d geographical point",
        ),
    ]

    # Run the above tests.
    for a_value in values_from_neomodel:
        expected_point = neo4j.spatial.Point(tuple(a_value[0].coords[0]))
        expected_point.srid = CRS_TO_SRID[a_value[0].crs]
        deflated_point = neomodel.contrib.spatial_properties.PointProperty(
            crs=a_value[0].crs
        ).deflate(a_value[0])
        basic_type_assertions(
            expected_point,
            deflated_point,
            "{}, received {}".format(a_value[1], deflated_point),
            check_neo4j_points=True,
        )


def test_default_value():
    """
    Tests that the default value passing mechanism works as expected with NeomodelPoint values.
    :return:
    """

    def get_some_point():
        return neomodel.contrib.spatial_properties.NeomodelPoint(
            (random.random(), random.random())
        )

    class LocalisableEntity(neomodel.StructuredNode):
        """
        A very simple entity to try out the default value assignment.
        """

        identifier = neomodel.UniqueIdProperty()
        location = neomodel.contrib.spatial_properties.PointProperty(
            crs="cartesian", default=get_some_point
        )

    # Neo4j versions lower than 3.4.0 do not support Point. In that case, skip the test.
    check_and_skip_neo4j_least_version(
        340, "This version does not support spatial data types."
    )

    # Save an object
    an_object = LocalisableEntity().save()
    coords = an_object.location.coords[0]
    # Retrieve it
    retrieved_object = LocalisableEntity.nodes.get(identifier=an_object.identifier)
    # Check against an independently created value
    assert (
        retrieved_object.location
        == neomodel.contrib.spatial_properties.NeomodelPoint(coords)
    ), ("Default value assignment failed.")


def test_array_of_points():
    """
    Tests that Arrays of Points work as expected.

    :return:
    """

    class AnotherLocalisableEntity(neomodel.StructuredNode):
        """
        A very simple entity with an array of locations
        """

        identifier = neomodel.UniqueIdProperty()
        locations = neomodel.ArrayProperty(
            neomodel.contrib.spatial_properties.PointProperty(crs="cartesian")
        )

    # Neo4j versions lower than 3.4.0 do not support Point. In that case, skip the test.
    check_and_skip_neo4j_least_version(
        340, "This version does not support spatial data types."
    )

    an_object = AnotherLocalisableEntity(
        locations=[
            neomodel.contrib.spatial_properties.NeomodelPoint((0.0, 0.0)),
            neomodel.contrib.spatial_properties.NeomodelPoint((1.0, 0.0)),
        ]
    ).save()

    retrieved_object = AnotherLocalisableEntity.nodes.get(
        identifier=an_object.identifier
    )

    assert (
        type(retrieved_object.locations) is list
    ), "Array of Points definition failed."
    assert retrieved_object.locations == [
        neomodel.contrib.spatial_properties.NeomodelPoint((0.0, 0.0)),
        neomodel.contrib.spatial_properties.NeomodelPoint((1.0, 0.0)),
    ], "Array of Points incorrect values."


def test_simple_storage_retrieval():
    """
    Performs a simple Create, Retrieve via .save(), .get() which, due to the way Q objects operate, tests the
    __copy__, __deepcopy__ operations of NeomodelPoint.
    :return:
    """

    class TestStorageRetrievalProperty(neomodel.StructuredNode):
        uid = neomodel.UniqueIdProperty()
        description = neomodel.StringProperty()
        location = neomodel.contrib.spatial_properties.PointProperty(crs="cartesian")

    # Neo4j versions lower than 3.4.0 do not support Point. In that case, skip the test.
    check_and_skip_neo4j_least_version(
        340, "This version does not support spatial data types."
    )

    a_restaurant = TestStorageRetrievalProperty(
        description="Milliways",
        location=neomodel.contrib.spatial_properties.NeomodelPoint((0, 0)),
    ).save()

    a_property = TestStorageRetrievalProperty.nodes.get(
        location=neomodel.contrib.spatial_properties.NeomodelPoint((0, 0))
    )

    assert a_restaurant.description == a_property.description

def test_equality_with_other_objects():
    """
    Performs equality tests and ensures tha ``NeomodelPoint`` can be compared with ShapelyPoint and NeomodelPoint only.
    """
    try:
        import shapely.geometry
        from shapely import __version__
    except ImportError:
        pytest.skip("Shapely module not present")

    if int("".join(__version__.split(".")[0:3])) < 200:
        pytest.skip(f"Shapely 2.0 not present (Current version is {__version__}")

    assert neomodel.contrib.spatial_properties.NeomodelPoint((0,0)) == neomodel.contrib.spatial_properties.NeomodelPoint(x=0, y=0)
    assert neomodel.contrib.spatial_properties.NeomodelPoint((0,0)) == shapely.geometry.Point((0,0))

