"""
Provides a test case for issue 374 - "Support for Point property type".

For more information please see: https://github.com/neo4j-contrib/neomodel/issues/374
"""

import neomodel
import pytest
import neo4j.v1
from .test_spatial_datatypes import basic_type_assertions
import random


def test_spatial_point_property():
    """
    Tests that specific modes of instantiation fail as expected.

    :return:
    """
    with pytest.raises(ValueError, message='Expected ValueError("Invalid CRS (CRS not specified)")'):
        a_point_property = neomodel.PointProperty()

    with pytest.raises(ValueError, message='Expected ValueError("Invalid CRS (CRS not acceptable)")'):
        a_point_property = neomodel.PointProperty(crs='crs_isaak')

    with pytest.raises(TypeError, message='Expected TypeError("Invalid default value")'):
        a_point_property = neomodel.PointProperty(default=(0.0, 0.0), crs='cartesian')


def test_inflate():
    """
    Tests that the marshalling from neo4j to neomodel data types works as expected.

    :return:
    """

    # The test is repeatable enough to try and standardise it. The same test is repeated with the assertions in
    # `basic_type_assertions` and different messages to be able to localise the exception.
    #
    # Array of points to inflate and messages when things go wrong
    values_from_db = [(neo4j.v1.spatial.CartesianPoint((0.0, 0.0)),
                       'Expected Neomodel 2d cartesian point when inflating 2d cartesian neo4j point'),
                      (neo4j.v1.spatial.CartesianPoint((0.0, 0.0, 0.0)),
                       'Expected Neomodel 3d cartesian point when inflating 3d cartesian neo4j point'),
                      (neo4j.v1.spatial.WGS84Point((0.0, 0.0)),
                       'Expected Neomodel 2d geographical point when inflating 2d geographical neo4j point'),
                      (neo4j.v1.spatial.WGS84Point((0.0, 0.0, 0.0)),
                       'Expected Neomodel 3d geographical point inflating 3d geographical neo4j point')]

    # Run the above tests
    for a_value in values_from_db:
        expected_point = neomodel.NeomodelPoint(tuple(a_value[0]),
                                                crs=neomodel.spatial_properties.SRID_TO_CRS[a_value[0].srid])
        inflated_point = neomodel.PointProperty(crs=neomodel.spatial_properties.SRID_TO_CRS[a_value[0].srid]).inflate(
                                                a_value[0])
        basic_type_assertions(expected_point, inflated_point, '{}, received {}'.format(a_value[1], inflated_point))


def test_deflate():
    """
    Tests that the marshalling from neomodel to neo4j data types works as expected
    :return:
    """
    # Please see inline comments in `test_inflate`. This test function is 90% to that one with very minor differences.
    #
    CRS_TO_SRID = dict([(value, key) for key, value in neomodel.spatial_properties.SRID_TO_CRS.items()])
    # Values to construct and expect during deflation
    values_from_neomodel = [(neomodel.NeomodelPoint((0.0, 0.0), crs='cartesian'),
                             'Expected Neo4J 2d cartesian point when deflating Neomodel 2d cartesian point'),
                            (neomodel.NeomodelPoint((0.0, 0.0, 0.0), crs='cartesian-3d'),
                             'Expected Neo4J 3d cartesian point when deflating Neomodel 3d cartesian point'),
                            (neomodel.NeomodelPoint((0.0,0.0), crs='wgs-84'),
                             'Expected Neo4J 2d geographical point when deflating Neomodel 2d geographical point'),
                            (neomodel.NeomodelPoint((0.0, 0.0, 0.0), crs='wgs-84-3d'),
                             'Expected Neo4J 3d geographical point when deflating Neomodel 3d geographical point')]

    # Run the above tests.
    for a_value in values_from_neomodel:
        expected_point = neo4j.v1.spatial.Point(tuple(a_value[0].coords[0]))
        expected_point.srid = CRS_TO_SRID[a_value[0].crs]
        deflated_point = neomodel.PointProperty(crs=a_value[0].crs).deflate(a_value[0])
        basic_type_assertions(expected_point, deflated_point, '{}, received {}'.format(a_value[1], deflated_point),
                              check_neo4j_points=True)


def test_default_value():
    """
    Tests that the default value passing mechanism works as expected with NeomodelPoint values.
    :return:
    """

    def get_some_point():
        return neomodel.NeomodelPoint((random.random(),random.random()))

    class LocalisableEntity(neomodel.StructuredNode):
        """
        A very simple entity to try out the default value assignment.
        """
        identifier = neomodel.UniqueIdProperty()
        location = neomodel.PointProperty(crs='cartesian', default=get_some_point)

    # Save an object
    an_object = LocalisableEntity().save()
    coords = an_object.location.coords[0]
    # Retrieve it
    retrieved_object = LocalisableEntity.nodes.get(identifier=an_object.identifier)
    # Check against an independently created value
    assert retrieved_object.location == neomodel.NeomodelPoint(coords), "Default value assignment failed."


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
        locations = neomodel.ArrayProperty(neomodel.PointProperty(crs='cartesian'))

    an_object = AnotherLocalisableEntity(locations=
                                         [neomodel.NeomodelPoint((0.0,0.0)), neomodel.NeomodelPoint((1.0,0.0))]).save()

    retrieved_object = AnotherLocalisableEntity.nodes.get(identifier=an_object.identifier)
    assert type(retrieved_object.locations) is list, "Array of Points definition failed."
    assert retrieved_object.locations == [neomodel.NeomodelPoint((0.0,0.0)), neomodel.NeomodelPoint((1.0,0.0))], \
        "Array of Points incorrect values."
