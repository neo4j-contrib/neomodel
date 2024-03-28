"""
Provides a test case for data types required by issue 374 - "Support for Point property type".

At the moment, only one new datatype is offered: NeomodelPoint

For more information please see: https://github.com/neo4j-contrib/neomodel/issues/374
"""

import os

import pytest
import shapely

import neomodel
import neomodel.contrib.spatial_properties
from neomodel.util import version_tag_to_integer


def check_and_skip_neo4j_least_version(required_least_neo4j_version, message):
    """
    Checks if the NEO4J_VERSION is at least `required_least_neo4j_version` and skips a test if not.

    WARNING: If the NEO4J_VERSION variable is not set, this function returns True, allowing the test to go ahead.

    :param required_least_neo4j_version: The least version to check. This must be the numberic representation of the
    version. That is: '3.4.0' would be passed as 340.
    :type required_least_neo4j_version: int
    :param message: An informative message as to why the calling test had to be skipped.
    :type message: str
    :return: A boolean value of True if the version reported is at least `required_least_neo4j_version`
    """
    if "NEO4J_VERSION" in os.environ:
        if (
            version_tag_to_integer(os.environ["NEO4J_VERSION"])
            < required_least_neo4j_version
        ):
            pytest.skip(
                "Neo4j version: {}. {}."
                "Skipping test.".format(os.environ["NEO4J_VERSION"], message)
            )


def basic_type_assertions(
    ground_truth, tested_object, test_description, check_neo4j_points=False
):
    """
    Tests that `tested_object` has been created as intended.

    :param ground_truth: The object as it is supposed to have been created.
    :type ground_truth: NeomodelPoint or neo4j.v1.spatial.Point
    :param tested_object: The object as it results from one of the contructors.
    :type tested_object: NeomodelPoint or neo4j.v1.spatial.Point
    :param test_description: A brief description of the test being performed.
    :type test_description: str
    :param check_neo4j_points: Whether to assert between NeomodelPoint or neo4j.v1.spatial.Point objects.
    :type check_neo4j_points: bool
    :return:
    """
    if check_neo4j_points:
        assert isinstance(
            tested_object, type(ground_truth)
        ), "{} did not return Neo4j Point".format(test_description)
        assert (
            tested_object.srid == ground_truth.srid
        ), "{} does not have the expected SRID({})".format(
            test_description, ground_truth.srid
        )
        assert len(tested_object) == len(
            ground_truth
        ), "Dimensionality mismatch. Expected {}, had {}".format(
            len(ground_truth.coords), len(tested_object.coords)
        )
    else:
        assert isinstance(
            tested_object, type(ground_truth)
        ), "{} did not return NeomodelPoint".format(test_description)
        assert (
            tested_object.crs == ground_truth.crs
        ), "{} does not have the expected CRS({})".format(
            test_description, ground_truth.crs
        )
        assert len(tested_object.coords[0]) == len(
            ground_truth.coords[0]
        ), "Dimensionality mismatch. Expected {}, had {}".format(
            len(ground_truth.coords[0]), len(tested_object.coords[0])
        )


# Object Construction
def test_coord_constructor():
    """
    Tests all the possible ways by which a NeomodelPoint can be instantiated successfully via passing coordinates.
    :return:
    """

    # Neo4j versions lower than 3.4.0 do not support Point. In that case, skip the test.
    check_and_skip_neo4j_least_version(
        340, "This version does not support spatial data types."
    )

    # Implicit cartesian point with coords
    ground_truth_object = neomodel.contrib.spatial_properties.NeomodelPoint((0.0, 0.0))
    new_point = neomodel.contrib.spatial_properties.NeomodelPoint((0.0, 0.0))
    basic_type_assertions(
        ground_truth_object,
        new_point,
        "Implicit 2d cartesian point instantiation",
    )

    ground_truth_object = neomodel.contrib.spatial_properties.NeomodelPoint(
        (0.0, 0.0, 0.0)
    )
    new_point = neomodel.contrib.spatial_properties.NeomodelPoint((0.0, 0.0, 0.0))
    basic_type_assertions(
        ground_truth_object,
        new_point,
        "Implicit 3d cartesian point instantiation",
    )

    # Explicit geographical point with coords
    ground_truth_object = neomodel.contrib.spatial_properties.NeomodelPoint(
        (0.0, 0.0), crs="wgs-84"
    )
    new_point = neomodel.contrib.spatial_properties.NeomodelPoint(
        (0.0, 0.0), crs="wgs-84"
    )
    basic_type_assertions(
        ground_truth_object,
        new_point,
        "Explicit 2d geographical point with tuple of coords instantiation",
    )

    ground_truth_object = neomodel.contrib.spatial_properties.NeomodelPoint(
        (0.0, 0.0, 0.0), crs="wgs-84-3d"
    )
    new_point = neomodel.contrib.spatial_properties.NeomodelPoint(
        (0.0, 0.0, 0.0), crs="wgs-84-3d"
    )
    basic_type_assertions(
        ground_truth_object,
        new_point,
        "Explicit 3d geographical point with tuple of coords instantiation",
    )

    # Cartesian point with named arguments
    ground_truth_object = neomodel.contrib.spatial_properties.NeomodelPoint(
        x=0.0, y=0.0
    )
    new_point = neomodel.contrib.spatial_properties.NeomodelPoint(x=0.0, y=0.0)
    basic_type_assertions(
        ground_truth_object,
        new_point,
        "Cartesian 2d point with named arguments",
    )

    ground_truth_object = neomodel.contrib.spatial_properties.NeomodelPoint(
        x=0.0, y=0.0, z=0.0
    )
    new_point = neomodel.contrib.spatial_properties.NeomodelPoint(x=0.0, y=0.0, z=0.0)
    basic_type_assertions(
        ground_truth_object,
        new_point,
        "Cartesian 3d point with named arguments",
    )

    # Geographical point with named arguments
    ground_truth_object = neomodel.contrib.spatial_properties.NeomodelPoint(
        longitude=0.0, latitude=0.0
    )
    new_point = neomodel.contrib.spatial_properties.NeomodelPoint(
        longitude=0.0, latitude=0.0
    )
    basic_type_assertions(
        ground_truth_object,
        new_point,
        "Geographical 2d point with named arguments",
    )

    ground_truth_object = neomodel.contrib.spatial_properties.NeomodelPoint(
        longitude=0.0, latitude=0.0, height=0.0
    )
    new_point = neomodel.contrib.spatial_properties.NeomodelPoint(
        longitude=0.0, latitude=0.0, height=0.0
    )
    basic_type_assertions(
        ground_truth_object,
        new_point,
        "Geographical 3d point with named arguments",
    )


def test_copy_constructors():
    """
    Tests all the possible ways by which a NeomodelPoint can be instantiated successfully via a copy constructor call.

    :return:
    """

    # Neo4j versions lower than 3.4.0 do not support Point. In that case, skip the test.
    check_and_skip_neo4j_least_version(
        340, "This version does not support spatial data types."
    )

    # Instantiate from Shapely point

    # Implicit cartesian from shapely point
    ground_truth = neomodel.contrib.spatial_properties.NeomodelPoint(
        (0.0, 0.0), crs="cartesian"
    )
    shapely_point = shapely.geometry.Point((0.0, 0.0))
    new_point = neomodel.contrib.spatial_properties.NeomodelPoint(shapely_point)
    basic_type_assertions(
        ground_truth, new_point, "Implicit cartesian by shapely Point"
    )

    # Explicit geographical by shapely point
    ground_truth = neomodel.contrib.spatial_properties.NeomodelPoint(
        (0.0, 0.0, 0.0), crs="wgs-84-3d"
    )
    shapely_point = shapely.geometry.Point((0.0, 0.0, 0.0))
    new_point = neomodel.contrib.spatial_properties.NeomodelPoint(
        shapely_point, crs="wgs-84-3d"
    )
    basic_type_assertions(
        ground_truth, new_point, "Explicit geographical by shapely Point"
    )

    # Copy constructor for NeomodelPoints
    ground_truth = neomodel.contrib.spatial_properties.NeomodelPoint((0.0, 0.0))
    other_neomodel_point = neomodel.contrib.spatial_properties.NeomodelPoint((0.0, 0.0))
    new_point = neomodel.contrib.spatial_properties.NeomodelPoint(other_neomodel_point)
    basic_type_assertions(ground_truth, new_point, "NeomodelPoint copy constructor")


def test_prohibited_constructor_forms():
    """
    Tests all the possible forms by which construction of NeomodelPoints should fail.

    :return:
    """

    # Neo4j versions lower than 3.4.0 do not support Point. In that case, skip the test.
    check_and_skip_neo4j_least_version(
        340, "This version does not support spatial data types."
    )

    # Absurd CRS
    with pytest.raises(ValueError, match=r"Invalid CRS\(blue_hotel\)"):
        _ = neomodel.contrib.spatial_properties.NeomodelPoint((0, 0), crs="blue_hotel")

    # Absurd coord dimensionality
    with pytest.raises(
        ValueError,
    ):
        _ = neomodel.contrib.spatial_properties.NeomodelPoint(
            (0, 0, 0, 0, 0, 0, 0), crs="cartesian"
        )

    # Absurd datatype passed to copy constructor
    with pytest.raises(
        TypeError,
    ):
        _ = neomodel.contrib.spatial_properties.NeomodelPoint(
            "it don't mean a thing if it ain't got that swing",
            crs="cartesian",
        )

    # Trying to instantiate a point with any of BOTH x,y,z or longitude, latitude, height
    with pytest.raises(ValueError, match="Invalid instantiation via arguments"):
        _ = neomodel.contrib.spatial_properties.NeomodelPoint(
            x=0.0,
            y=0.0,
            longitude=0.0,
            latitude=2.0,
            height=-2.0,
            crs="cartesian",
        )

    # Trying to instantiate a point with absolutely NO parameters
    with pytest.raises(ValueError, match="Invalid instantiation via no arguments"):
        _ = neomodel.contrib.spatial_properties.NeomodelPoint()


def test_property_accessors_depending_on_crs_shapely_lt_2():
    """
    Tests that points are accessed via their respective accessors.

    :return:
    """

    # Neo4j versions lower than 3.4.0 do not support Point. In that case, skip the test.
    check_and_skip_neo4j_least_version(
        340, "This version does not support spatial data types."
    )

    # Check the version of Shapely installed to run the appropriate tests:
    try:
        from shapely import __version__
    except ImportError:
        pytest.skip("Shapely not installed")

    if int("".join(__version__.split(".")[0:3])) >= 200:
        pytest.skip("Shapely 2 is installed, skipping earlier version test")

    # Geometrical points only have x,y,z coordinates
    new_point = neomodel.contrib.spatial_properties.NeomodelPoint(
        (0.0, 0.0, 0.0), crs="cartesian-3d"
    )
    with pytest.raises(AttributeError, match=r'Invalid coordinate \("longitude"\)'):
        new_point.longitude
    with pytest.raises(AttributeError, match=r'Invalid coordinate \("latitude"\)'):
        new_point.latitude
    with pytest.raises(AttributeError, match=r'Invalid coordinate \("height"\)'):
        new_point.height

    # Geographical points only have longitude, latitude, height coordinates
    new_point = neomodel.contrib.spatial_properties.NeomodelPoint(
        (0.0, 0.0, 0.0), crs="wgs-84-3d"
    )
    with pytest.raises(AttributeError, match=r'Invalid coordinate \("x"\)'):
        new_point.x
    with pytest.raises(AttributeError, match=r'Invalid coordinate \("y"\)'):
        new_point.y
    with pytest.raises(AttributeError, match=r'Invalid coordinate \("z"\)'):
        new_point.z


def test_property_accessors_depending_on_crs_shapely_gte_2():
    """
    Tests that points are accessed via their respective accessors.

    :return:
    """

    # Neo4j versions lower than 3.4.0 do not support Point. In that case, skip the test.
    check_and_skip_neo4j_least_version(
        340, "This version does not support spatial data types."
    )

    # Check the version of Shapely installed to run the appropriate tests:
    try:
        from shapely import __version__
    except ImportError:
        pytest.skip("Shapely not installed")

    if int("".join(__version__.split(".")[0:3])) < 200:
        pytest.skip("Shapely < 2.0.0 is installed, skipping test")
    # Geometrical points only have x,y,z coordinates
    new_point = neomodel.contrib.spatial_properties.NeomodelPoint(
        (0.0, 0.0, 0.0), crs="cartesian-3d"
    )
    with pytest.raises(TypeError, match=r'Invalid coordinate \("longitude"\)'):
        new_point.longitude
    with pytest.raises(TypeError, match=r'Invalid coordinate \("latitude"\)'):
        new_point.latitude
    with pytest.raises(TypeError, match=r'Invalid coordinate \("height"\)'):
        new_point.height

    # Geographical points only have longitude, latitude, height coordinates
    new_point = neomodel.contrib.spatial_properties.NeomodelPoint(
        (0.0, 0.0, 0.0), crs="wgs-84-3d"
    )
    with pytest.raises(TypeError, match=r'Invalid coordinate \("x"\)'):
        new_point.x
    with pytest.raises(TypeError, match=r'Invalid coordinate \("y"\)'):
        new_point.y
    with pytest.raises(TypeError, match=r'Invalid coordinate \("z"\)'):
        new_point.z


def test_property_accessors():
    """
    Tests that points are accessed via their respective accessors and that these accessors return the right values.

    :return:
    """

    # Neo4j versions lower than 3.4.0 do not support Point. In that case, skip the test.
    check_and_skip_neo4j_least_version(
        340, "This version does not support spatial data types."
    )

    # Geometrical points
    new_point = neomodel.contrib.spatial_properties.NeomodelPoint(
        (0.0, 1.0, 2.0), crs="cartesian-3d"
    )
    assert new_point.x == 0.0, "Expected x coordinate to be 0.0"
    assert new_point.y == 1.0, "Expected y coordinate to be 1.0"
    assert new_point.z == 2.0, "Expected z coordinate to be 2.0"

    # Geographical points
    new_point = neomodel.contrib.spatial_properties.NeomodelPoint(
        (0.0, 1.0, 2.0), crs="wgs-84-3d"
    )
    assert new_point.longitude == 0.0, "Expected longitude to be 0.0"
    assert new_point.latitude == 1.0, "Expected latitude to be 1.0"
    assert new_point.height == 2.0, "Expected height to be 2.0"
