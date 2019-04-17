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
import neo4j.types.spatial

# If shapely is not installed, its import will fail and the spatial properties will not be available
try:
    from shapely.geometry import Point as ShapelyPoint
except ImportError:
    raise ImportError('NEOMODEL ERROR: Shapely not found. If required, you can install Shapely via '
                      '`pip install shapely`.')

from neomodel.properties import Property, validator

# Note: Depending on how Neo4J decides to handle the resolution of geographical points, these two
# private attributes might have to be updated in the future or removed altogether.
# They help in trying to resolve which class needs to be instantiated based on the data received from the dbms
# and doing it in a concise way that minimises errors.
#
# Acceptable Coordinate Reference Systems
ACCEPTABLE_CRS = ['cartesian', 'cartesian-3d', 'wgs-84', 'wgs-84-3d']
# A simple CRS to SRID mapping
SRID_TO_CRS = {7203: 'cartesian', 9157: 'cartesian-3d', 4326: 'wgs-84', 4979: 'wgs-84-3d'}


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

    # def __init__(self, *args, crs=None, x=None, y=None, z=None, latitude=None, longitude=None, height=None, **kwargs):
    def __init__(self, *args, **kwargs):
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

        # Python2.7 Workaround for the order that the arguments get passed to the functions
        crs = kwargs.pop('crs', None)
        x = kwargs.pop('x', None)
        y = kwargs.pop('y', None)
        z = kwargs.pop('z', None)
        longitude = kwargs.pop('longitude', None)
        latitude = kwargs.pop('latitude', None)
        height = kwargs.pop('height', None)

        _x, _y, _z = None, None, None

        # CRS validity check is common to both types of constructors that follow
        if crs is not None and crs not in ACCEPTABLE_CRS:
            raise ValueError('Invalid CRS({}). Expected one of {}'.format(crs, ','.join(ACCEPTABLE_CRS)))
        self._crs = crs

        # If positional arguments have been supplied, then this is a possible call to the copy constructor or
        # initialisation by a coordinate iterable as per ShapelyPoint constructor.
        if len(args):
            # If a coordinate iterable was passed, emulate a call with x,y[,z] parameters
            if isinstance(args[0],(tuple, list)):
                # Check dimensionality of tuple
                if len(args[0]) < 2 or len(args[0]) > 3:
                    raise ValueError('Invalid vector dimensions. Expected 2 or 3, received {}'.format(len(args[0])))
                x = args[0][0]
                y = args[0][1]
                if len(args[0]) == 3:
                    z = args[0][2]
            # If another "Point" was passed, then this is a call to the copy constructor
            elif isinstance(args[0], ShapelyPoint):
                super(NeomodelPoint, self).__init__(args[0])
                # If the other Point was a NeomodelPoint then it bears the CRS that is used to
                # interpret the points and this has to be carried over.
                if isinstance(args[0], NeomodelPoint):
                    self._crs = args[0]._crs
                else:
                    # This allows NeomodelPoint((0,0),crs="wgs-84") which will interpret the tuple as
                    # (longitude,latitude) even though it was not specified as such with the named arguments.
                    #
                    # NOTE: Notice the indexing on the coordinates `args[0].coords[0]`. Coordinates are always an
                    # iterable which for Points has length of 1 but for other geometrical objects (e.g. boundaries)
                    # might be longer. This will come back to bite you, if you assume that `coords` is what it pretends
                    # to be (i.e. coords gives access to the actual coordinates NOT an iterable).
                    #
                    if len(args[0].coords[0]) == 2:
                        if crs is None:
                            self._crs = 'cartesian'
                    elif len(args[0].coords[0]) == 3:
                        if crs is None:
                            self._crs = 'cartesian-3d'
                    else:
                        raise ValueError('Invalid vector dimensions. '
                                         'Expected 2 or 3, received {}'.format(len(args[0].coords[0])))
                return
            else:
                raise TypeError('Invalid object passed to copy constructor. '
                                'Expected NeomodelPoint or shapely Point, received {}'.format(type(args[0])))

        # Initialisation is either via x,y[,z] XOR longitude,latitude[,height]. Specifying both leads to an error.
        if (x is not None or y is not None or z is not None) and \
                (latitude is not None or longitude is not None or height is not None):
            raise ValueError('Invalid instantiation via arguments. '
                             'A Point can be defined either by x,y,z coordinates OR latitude,longitude,height but not '
                             'a combination of these terms')

        # Specifying no initialisation argument at this point in the constructor is flagged as an error
        if x is None and y is None and z is None and longitude is None and latitude is None and height is None:
            raise ValueError('Invalid instantiation via no arguments. '
                             'A Point needs default values either in x,y,z or longitude, latitude, height coordinates')

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

        # Geometrical Point Initialisation
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
            if '-3d' not in self._crs:
                super(NeomodelPoint, self).__init__((float(_x),float(_y)), **kwargs)
            else:
                raise ValueError("Invalid vector dimensions(2) for given CRS({}).".format(self._crs))
        else:
            if '-3d' in self._crs:
                super(NeomodelPoint, self).__init__((float(_x), float(_y), float(_z)), **kwargs)
            else:
                raise ValueError("Invalid vector dimensions(3) for given CRS({}).".format(self._crs))

    @property
    def crs(self):
        return self._crs

    @property
    def x(self):
        if not self._crs.startswith('cartesian'):
            raise AttributeError('Invalid coordinate ("x") for points defined over {}'.format(self.crs))
        return super(NeomodelPoint, self).x

    @property
    def y(self):
        if not self._crs.startswith('cartesian'):
            raise AttributeError('Invalid coordinate ("y") for points defined over {}'.format(self.crs))
        return super(NeomodelPoint, self).y

    @property
    def z(self):
        if not self._crs == 'cartesian-3d':
            raise AttributeError('Invalid coordinate ("z") for points defined over {}'.format(self.crs))
        return super(NeomodelPoint, self).z

    @property
    def latitude(self):
        if not self._crs.startswith('wgs-84'):
            raise AttributeError('Invalid coordinate ("latitude") for points defined over {}'.format(self.crs))
        return super(NeomodelPoint, self).y

    @property
    def longitude(self):
        if not self._crs.startswith('wgs-84'):
            raise AttributeError('Invalid coordinate ("longitude") for points defined over {}'.format(self.crs))
        return super(NeomodelPoint, self).x

    @property
    def height(self):
        if not self._crs == 'wgs-84-3d':
            raise AttributeError('Invalid coordinate ("height") for points defined over {}'.format(self.crs))
        return super(NeomodelPoint, self).z

    # The following operations are necessary here due to the way queries (and more importantly their parameters) get
    # combined and evaluated in neomodel. Specifically, query expressions get duplicated with deep copies and any valid
    # datatype values should also implement these operations.
    def __copy__(self):
        return NeomodelPoint(self)

    def __deepcopy__(self, memo):
        return NeomodelPoint(self)


class PointProperty(Property):
    """
    Validates points which can participate in spatial queries.
    """

    form_field_class = 'PointField'
    # The CRS that this property is expected to be expressed in.
    _crs = None

    def __init__(self, *args, **kwargs):
        """
        A Point property that requires at least its CRS to be known to offer proper validation.

        :param crs: Coordinate Reference System
        :type crs: str
        :param kwargs: Dictionary of arguments
        :type kwargs: dict
        """
        if 'crs' in kwargs:
            crs = kwargs['crs']
            del(kwargs['crs'])
        else:
            crs = None

        if crs is None or (crs not in ACCEPTABLE_CRS):
            raise ValueError('Invalid CRS({}). '
                             'Point properties require CRS to be one of {}'.format(crs, ','.join(ACCEPTABLE_CRS)))

        # If a default value is passed and it is not a callable, then make sure it is in the right type
        if 'default' in kwargs:
            if not hasattr(kwargs['default'], "__call__"):
                if not isinstance(kwargs['default'], NeomodelPoint):
                    raise TypeError('Invalid default value. '
                                    'Expected NeomodelPoint, received {}'.format(type(kwargs['default'])))

        super(PointProperty, self).__init__(*args, **kwargs)
        self._crs = crs

    @validator
    def inflate(self, value):
        """
        Handles the marshalling from Neo4J POINT to NeomodelPoint

        :param value: Value returned from the database
        :type value: Neo4J POINT
        :return: NeomodelPoint
        """
        if not isinstance(value,neo4j.types.spatial.Point):
            raise TypeError('Invalid datatype to inflate. Expected POINT datatype, received {}'.format(type(value)))

        try:
            value_point_crs = SRID_TO_CRS[value.srid]
        except KeyError:
            raise ValueError('Invalid SRID to inflate. '
                             'Expected one of {}, received {}'.format(SRID_TO_CRS.keys(), value.srid))

        if self._crs != value_point_crs:
            raise ValueError('Invalid CRS. '
                             'Expected POINT defined over {}, received {}'.format(self._crs, value_point_crs))
        # cartesian
        if value.srid == 7203:
            return NeomodelPoint(x=value.x, y=value.y)
        # cartesian-3d
        elif value.srid == 9157:
            return NeomodelPoint(x=value.x, y=value.y, z=value.z)
        # wgs-84
        elif value.srid == 4326:
            return NeomodelPoint(longitude=value.longitude, latitude=value.latitude)
        # wgs-83-3d
        elif value.srid == 4979:
            return NeomodelPoint(longitude=value.longitude, latitude=value.latitude, height=value.height)

    @validator
    def deflate(self, value):
        """
        Handles the marshalling from NeomodelPoint to Neo4J POINT

        :param value: The point that was assigned as value to a property in the model
        :type value: NeomodelPoint
        :return: Neo4J POINT
        """
        if not isinstance(value, NeomodelPoint):
            raise TypeError('Invalid datatype to deflate. Expected NeomodelPoint, received {}'.format(type(value)))

        if not value.crs == self._crs:
            raise ValueError('Invalid CRS. '
                             'Expected NeomodelPoint defined over {}, '
                             'received NeomodelPoint defined over {}'.format(self._crs, value.crs))

        if value.crs == 'cartesian-3d':
            return neo4j.types.spatial.CartesianPoint((value.x, value.y,  value.z))
        elif value.crs == 'cartesian':
            return neo4j.types.spatial.CartesianPoint((value.x,value.y))
        elif value.crs == 'wgs-84':
            return neo4j.types.spatial.WGS84Point((value.longitude, value.latitude))
        elif value.crs == 'wgs-84-3d':
            return neo4j.types.spatial.WGS84Point((value.longitude, value.latitude, value.height))
