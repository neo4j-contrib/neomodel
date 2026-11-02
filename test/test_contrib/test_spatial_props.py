from test.consts import SHAPELY_IS_NOT_INSTALLED_WARNING

import pytest

pytest.importorskip(
    "shapely",
    reason=SHAPELY_IS_NOT_INSTALLED_WARNING,
)

from neomodel.contrib.spatial_properties import NeomodelPoint


def test_failed_initialisation():
    """
    Tests that a NeomodelPoint cannot be instantiated in an erroneous state
    """

    # Must be instantiated with a meaningful CRS
    with pytest.raises(ValueError):
        p1 = NeomodelPoint(crs="blah")

    # Must be instantiated with the right dimensionality of coordinates (either 2 or 3)
    with pytest.raises(ValueError):
        p1 = NeomodelPoint([0, 0, 0, 0])

    with pytest.raises(ValueError):
        p1 = NeomodelPoint(
            [
                0,
            ]
        )

    # Copy constructor only on the right type of object
    with pytest.raises(TypeError):
        p1 = NeomodelPoint("Definitely not a Neomodel point")

    # Cannot be instantiated in a cartesian or geographical CRS at the same time
    with pytest.raises(ValueError):
        p1 = NeomodelPoint(x=0, y=0, z=0, longitude=0, latitude=0, height=0)

    # Cannot be instantiated without actually pointing somehwere in space
    with pytest.raises(ValueError):
        p1 = NeomodelPoint()

    # CRS and supplied arguments should match (3 for a 3d crs, 2 for a 2d crs)
    with pytest.raises(ValueError):
        p1 = NeomodelPoint(x=0, y=0, z=0, crs="cartesian")

    with pytest.raises(ValueError):
        p1 = NeomodelPoint(x=0, y=0, crs="cartesian-3d")


def test_succesful_initialisation():
    """
    Expected initialisation and copy constructor
    """

    p1 = NeomodelPoint(x=0, y=0)
    p2 = NeomodelPoint(x=0, y=0, z=0)
    p3 = NeomodelPoint(longitude=0, latitude=0)
    p4 = NeomodelPoint(longitude=0, latitude=0, height=0)
    p5 = NeomodelPoint([0, 0])
    p6 = NeomodelPoint([0, 0, 0])
    p7 = NeomodelPoint(p6)

    assert p1.crs == "cartesian"
    assert p1.x == 0
    assert p1.y == 0
    assert p2.crs == "cartesian-3d"
    assert p2.x == 0
    assert p2.y == 0
    assert p2.z == 0

    assert p5.crs == "cartesian"
    assert p5.x == 0
    assert p5.y == 0
    assert p6.crs == "cartesian-3d"
    assert p6.x == 0
    assert p6.y == 0
    assert p6.z == 0

    assert p3.crs == "wgs-84"
    assert p3.longitude == 0
    assert p3.latitude == 0
    assert p4.crs == "wgs-84-3d"
    assert p4.longitude == 0
    assert p4.latitude == 0
    assert p4.height == 0

    assert p7.crs == "cartesian-3d"
    assert p7.x == 0
    assert p7.y == 0
    assert p7.z == 0


def test_property_access():
    """
    Points initialised as 2d cannot offer access to 3d coordinates
    """

    p1 = NeomodelPoint(x=0, y=0)
    p2 = NeomodelPoint(longitude=0, latitude=0, height=0)

    with pytest.raises(TypeError):
        assert p1.longitude == 0

    with pytest.raises(TypeError):
        assert p1.latitude == 0

    with pytest.raises(TypeError):
        assert p1.height == 0

    with pytest.raises(TypeError):
        assert p2.x == 0

    with pytest.raises(TypeError):
        assert p2.y == 0

    with pytest.raises(TypeError):
        assert p2.z == 0


def test_equality_success():
    """
    Points with identical coordinates and CRS are equal in value
    """
    p1 = NeomodelPoint(x=0, y=0, z=0)
    p2 = NeomodelPoint(x=0, y=0, z=0)

    assert p1 == p2


def test_equality_fails():
    """
    Points are comparable only with points
    """
    p1 = NeomodelPoint(x=0, y=0, z=0)

    with pytest.raises(ValueError):
        assert p1 == 4


def test_equality_successful():
    """
    Points with identical coordinates and CRS are equal in value
    """
    p1 = NeomodelPoint(x=0, y=0, z=0)
    p2 = NeomodelPoint(x=0, y=0, z=0)
    p3 = NeomodelPoint(longitude=0, latitude=0, height=0)
    p4 = NeomodelPoint(longitude=0, latitude=0, height=0)

    assert p1 == p2
    assert p3 == p4
    assert p1 != p4
    assert p3 != p2
