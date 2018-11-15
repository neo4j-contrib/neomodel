"""

    Data types and validators (PointProperty) for working with neo4j's spatial data types through neomodel.

    `spatial_properties` offers two classes: NeomodelPoint, PointProperty that marshal data to and from a neo4j dbms,
    with the added capability of being Shapely objects. Therefore, points retrieved with Neomodel can readily be used
    in further geometric (via Shapely) or geospatial (via PySAL) operations.

    * More information on Neo4J's spatial data types:
        * https://neo4j.com/docs/developer-manual/3.4/cypher/syntax/spatial/

    * More information on the Python driver's data types:
        * https://neo4j.com/docs/api/python-driver/1.7-preview/types.html#spatial-types

    * More information about Shapely's spatial data types:
        * http://toblerity.org/shapely/manual.html#geometric-objects

    * More information about PySAL through Shapely:
        * https://pysal.readthedocs.io/en/latest/users/tutorials/shapely.html
"""

__author__ = "Athanasios Anastasiou"

import neo4j.v1
from shapely.geometry import Point as ShapelyPoint
from neomodel.properties import Property, validator


class NeomodelPoint(ShapelyPoint):
    """
    Abstracts the Point spatial data type of Neo4j.

    Note:
    At the time of writing, Neo4j supports 2 main variants of Point:
        1. A generic point defined over a Cartesian plane
            * The minimum data to define a point is x, y [,z] when crs is either "cartesian" or "cartesian-3d"
        2. A generic point defined over the WGS84 ellipsoid
            * The minimum data to define a point is longitude, latitude [,Height] and the crs is then assumed
              to be "wgs-84".
    """

    def __init__(self, *args, crs=None, x=None, y=None, z=None, latitude=None, longitude=None, height=None, **kwargs):
        """
        Creates a NeomodelPoint.

        :param args: Positional arguments to emulate the behaviour of Shapely's Point (and specifically the copy
        constructor)
        :type args: list
        :param crs: Coordinate Reference System, must be one of ['cartesian', 'cartesian-3d', 'wgs-84', 'wgs-84-3d']
        :type crs: str
        :param x: x coordinate of point
        :type x: float
        :param y: y coordinate of point
        :type y: float
        :param z: z coordinate of point if the crs is cartesian-3d
        :type z: float
        :param latitude: Latitude of point
        :type latitude: float
        :param longitude: Longitude of point
        :type longitude: float
        :param height: Height of point if the crs is wgs-84-3d
        :type height: float
        :param kwargs: Dictionary of keyword arguments
        :type kwargs: dict
        """
        self._acceptable_crs = ['cartesian', 'cartesian-3d', 'wgs-84', 'wgs-84-3d']
        _x, _y, _z = None, None, None

        # CRS validity check is common to the type of constructor call that follows
        if crs not in self._acceptable_crs:
            raise ValueError('CRS({}) not one of {}'.format(crs, self._acceptable_crs.join(',')))
        self._crs = crs

        # If positional arguments have been supplied, then this is a possible call to the copy constructor or
        # initialisation by a coordinate iterable
        if len(args):
            # If a coordinate iterable was passed, emulate a call with x,y[,z] parameters
            if isinstance(args[0],(tuple, list)):
                x = args[0][0]
                y = args[0][1]
                if len(args[0])>2:
                    z = args[0][2]
            # If another "Point" was passed, then this is a call to the copy constructor
            elif isinstance(args[0], ShapelyPoint):
                super().__init__(args[0])
                # A NeomodelPoint bears the CRS that is used to interpret the points and this has to be carried over
                if isinstance(args[0], NeomodelPoint):
                    self._crs = args[0]._crs
                else:
                    # This allows NeomodelPoint((0,0),crs="wgs-84") which will interpret the tuple as
                    # (longitude,latitude) even though it was not specified as such with the named arguments.
                    if len(args[0]) == 2:
                        if crs is None:
                            self._crs = 'cartesian'
                    elif len(args[0]) == 3:
                        if crs is None:
                            self._crs = 'cartesian-3d'
                    else:
                        # Flag error
                        pass
                return

        # Initialisation is either via x,y[,z] XOR longitude,latitude[,height]. Specifying both leads to an error.
        if (x is not None or y is not None or z is not None) and \
                (latitude is not None or longitude is not None or height is not None):
            raise ValueError('A Point can be defined either by x,y,z coordinates OR latitude,longitude,height but not '
                             'a combination of these terms')

        # Specifying no initialisation argument at this point in the constructor is flagged as an error
        if x is None and y is None and z is None and longitude is None and latitude is None and height is None:
            raise ValueError('A Point needs default values either in x,y,z or longitude, latitude, height coordinates')

        # Geographical Point Initialisation
        if latitude is not None and longitude is not None:
            if height is not None:
                if self._crs is None:
                    self._crs = 'wgs-84-3d'
                _z = height
            else:
                if self._crs is None:
                    self._crs = 'wgs-84'
            _x = longitude
            _y = latitude

        # Geometrical Point initialisation
        if x is not None and y is not None:
            if z is not None:
                if self._crs is None:
                    self._crs = 'cartesian-3d'
                _z = z
            else:
                if self._crs is None:
                    self._crs = 'cartesian'
            _x = x
            _y = y

        if _z is None:
            super().__init__(float(_x),float(_y), **kwargs)
        else:
            super().__init__(float(_x), float(_y), float(_z), **kwargs)

    @property
    def crs(self):
        return self._crs

    @crs.setter
    def crs(self, value):
        if value not in self._acceptable_crs:
            raise ValueError('Invalid CRS. Expected one of {} received {}'.format(self._acceptable_crs.join(','), value))
        self._crs = value

    @property
    def x(self):
        if not self._crs.startswith('cartesian'):
            raise ValueError('Invalid coordinate ("x") for points defined over {}'.format(self.crs))
        return super().x

    @property
    def y(self):
        if not self._crs.startswith('cartesian'):
            raise ValueError('Invalid coordinate ("y") for points defined over {}'.format(self.crs))
        return super().y

    @property
    def z(self):
        if not self._crs == 'cartesian-3d':
            raise ValueError('Invalid coordinate ("z") for points defined over {}'.format(self.crs))
        return super().z

    @property
    def latitude(self):
        if not self._crs.startswith('wgs-84'):
            raise ValueError('Invalid coordinate ("latitude") for points defined over {}'.format(self.crs))
        return super().y

    @property
    def longitude(self):
        if not self._crs.startswith('wgs-84'):
            raise ValueError('Invalid coordinate ("longitude") for points defined over {}'.format(self.crs))
        return super().x

    @property
    def height(self):
        if not self._crs == 'wgs-84-3d':
            raise ValueError('Invalid coordinate ("height") for points defined over {}'.format(self.crs))
        return super().z


class PointProperty(Property):
    """
    Validates points which can participate in spatial queries.
    """

    form_field_class = 'PointField'
    # The CRS that this property is expected to be expressed in.
    _crs = None

    def __init__(self, crs=None, **kwargs):
        """
        A Point property that requires at least its CRS to be known to offer proper validation.
        :param crs: Coordinate Reference System
        :type crs: str
        :param kwargs: Dictionary of arguments
        :type kwargs: dict
        """
        if crs is None:
            raise ValueError('Point properties require their CRS to be set')
        super().__init__(**kwargs)
        self._crs = crs

    @validator
    def inflate(self, value):
        """
        Handles the marshalling from Neo4J POINT to NeomodelPoint

        :param value: Value returned from the database
        :type value: Neo4J POINT
        :return: NeomodelPoint
        """
        if not isinstance(value,neo4j.v1.spatial.Point):
            raise ValueError('Expected POINT datatype, received {}'.format(type(value)))
        if value.srid == 7203: #cartesian
            if self._crs != 'cartesian':
                raise ValueError('Expected POINT defined over {}, got {}'.format(self._crs,type(value)))
            return NeomodelPoint(x=value.x, y=value.y)
        elif value.srid == 9157: #cartesian-3d
            if self._crs != 'cartesian-3d':
                raise ValueError('Expected POINT defined over {}, got {}'.format(self._crs,type(value)))
            return NeomodelPoint(x=value.x, y=value.y, z=value.z)
        elif value.srid == 4979: #wgs-84
            if self._crs != 'wgs-84':
                raise ValueError('Expected POINT defined over {}, got {}'.format(self._crs,type(value)))
            return NeomodelPoint(longitude=value.longitude, latitude=value.latitude)
        elif value.srid == 4326: #wgs-83-3d
            if self._crs != 'wgs-84-3d':
                raise ValueError('Expected POINT defined over {}, got {}'.format(self._crs,type(value)))
            return NeomodelPoint(longitude=value.longitude, latitude=value.latitude, height=value.height)
        raise ValueError('Unexpected srid({}) received'.format(value.srid))

    @validator
    def deflate(self, value):
        """
        Handles the marshalling from NeomodelPoint to Neo4J POINT

        :param value: The point that was assigned as value to a property in the model
        :type value: NeomodelPoint
        :return: Neo4J POINT
        """
        if not isinstance(value, NeomodelPoint):
            raise ValueError('Expected NeomodelPoint, received {}'.format(type(value)))
        if not value.crs == self._crs:
            raise ValueError('Expected NeomodelPoint defined over {}, got NeomodelPoint defined over {}'
                             .format(self._crs, value.crs))

        if value.crs == 'cartesian-3d':
            return neo4j.v1.spatial.CartesianPoint((value.x, value.y,  value.z))
        elif value.crs == 'cartesian':
            return neo4j.v1.spatial.CartesianPoint((value.x,value.y))
        elif value.crs == 'wgs-84':
            return neo4j.v1.spatial.WGS84Point((value.longitude, value.latitude))
        elif value.crs == 'wgs-84-3d':
            return neo4j.v1.spatial.WGS84Point((value.longitude, value.latitude, value.height))