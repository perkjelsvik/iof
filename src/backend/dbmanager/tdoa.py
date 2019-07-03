# Python built-in modules and packages
from dataclasses import dataclass
from typing import Optional, Tuple, Union

# Third-party modules and packages
import numpy as np
import utm

# dict to convert meters. Conversion factors from google search: "1 meter to {unit}"
_conversion = {
    "m": 1,
    "cm": 100,
    "km": 0.001,
    "mi": 0.000_621_371_192,
    "nmi": 0.000_539_956_803,
    "ft": 3.280_839_9,
    "in": 39.370_078_7,
}


# Definitions of dataclasses used in this module.
@dataclass
class LatLong:
    lat: float
    lon: float


@dataclass
class Point:
    x: float
    y: float


@dataclass
class Circle:
    center: Point
    radius: float


@dataclass
class CoordXYZ(Point):
    z: float
    unit: str = "m"


@dataclass
class CoordUTM:
    easting: float
    northing: float


@dataclass
class StationData:
    """StationData class used for positioning.

    StationData is used to construct and filter data on a valid form to then try and
    perform positioning based on the stationdata and other data provided. It is also
    used to convert between UTM, latlong and local XYZ-cartesian coordinate system.
    And it is used in verification of position candidates (station positions).

    Attributes:
        TBR_i: Integer ID of stations (where i = A, B, C).
        pos_i: LatLong position of stations (where i = A, B, C).
        depth: Shared depth of stations
        theta: Angle to rotate back from local xyz-system to UTM.
        utm_zone_num: Integer used in conversion from utm to latlong.
        utm_zone_let: String used in conversion from utm to latlong.
        utm_i: UTM Northing and Easting of stations (where i = A, B, C).
        xyz_i: XYZ-coordinates of stations (where i = A, B, C).
    """

    TBR_A: int
    TBR_B: int
    TBR_C: int
    pos_A: LatLong
    pos_B: LatLong
    pos_C: LatLong
    depth: float
    theta: float = 0
    utm_zone_num: int = 0
    utm_zone_let: str = ""
    utm_A: CoordUTM = CoordUTM(0, 0)
    utm_B: CoordUTM = CoordUTM(0, 0)
    utm_C: CoordUTM = CoordUTM(0, 0)
    xyz_A: CoordXYZ = CoordXYZ(0.0, 0.0, 0.0)
    xyz_B: CoordXYZ = CoordXYZ(0.0, 0.0, 0.0)
    xyz_C: CoordXYZ = CoordXYZ(0.0, 0.0, 0.0)

    def __post_init__(self):
        """Adds utm coordinates by converting latlong, and xyz by converting utm."""
        self._convert_latlong_to_utm()
        self._convert_utm_to_xyz()

    def _convert_latlong_to_utm(self):
        """Performs conversion between latlong and utm."""
        utm_A = utm.from_latlon(self.pos_A.lat, self.pos_A.lon)
        utm_B = utm.from_latlon(self.pos_B.lat, self.pos_B.lon)
        utm_C = utm.from_latlon(self.pos_C.lat, self.pos_C.lon)
        self.utm_A = CoordUTM(easting=utm_A[0], northing=utm_A[1])
        self.utm_B = CoordUTM(easting=utm_B[0], northing=utm_B[1])
        self.utm_C = CoordUTM(easting=utm_C[0], northing=utm_C[1])
        self.utm_zone_num = utm_A[2]
        self.utm_zone_let = utm_A[3]

    def _convert_utm_to_xyz(self):
        """Performs conversion between utm and local coordinate system XYZ."""
        # Unpack station data variables
        A, B, C = self.utm_A, self.utm_B, self.utm_C
        z = self.depth

        # Find the distance from B to A and from C to A
        BA = np.array([B.easting - A.easting, B.northing - A.northing])
        CA = np.array([C.easting - A.easting, C.northing - A.northing])

        # Find the angle to rotate B to x=0, and which angle to rotate C with
        theta_b, r_b = _cart2pol(BA[0], BA[1])
        theta_c, r_c = _cart2pol(CA[0], CA[1])
        theta_c_t = theta_c - theta_b

        # Find xy-coordinate for C
        C_x, C_y = _pol2cart(theta_c_t, r_c)

        # Add xyz-coordinates to station_data
        self.xyz_A = CoordXYZ(x=0, y=0, z=z)
        self.xyz_B = CoordXYZ(x=r_b, y=0, z=z)
        self.xyz_C = CoordXYZ(x=C_x, y=C_y, z=z)
        self.theta = theta_b  # needed for transformation back to latlong


@dataclass
class Timestamps:
    """Timestamps class used for positioning.

    Timestamps is used solve TDOA hyperbola positoning, where its attributes represent
    time of arrival for each station.

    Attributes:
        sec_i: Integer UTC timestamp (seconds) Time of Arrival (where i = A, B, C).
        msec_i: Integer millisecond Time of Arrival (where i = A, B, C).
    """

    sec_a: int
    sec_b: int
    sec_c: int
    msec_a: int
    msec_b: int
    msec_c: int


# *------------------------------------------------*
# | "private" helper-functions used by this module |
# *------------------------------------------------*


def _cart2pol(x: float, y: float) -> Tuple[float, float]:
    r = np.sqrt(x ** 2 + y ** 2)
    theta = np.arctan2(y, x)
    return (theta, r)


def _pol2cart(theta: float, r: float) -> Tuple[float, float]:
    x = r * np.cos(theta)
    y = r * np.sin(theta)
    return (x, y)


def _convert_xyz_unit(xyz: CoordXYZ, unit: str) -> CoordXYZ:
    """Converts xyz position unit to desired unit.

    Uses dict '_conversion' to convert dataclass 'CoordXYZ' instance to desired unit.
    Dictionary with unit mapping is defined as a 'private' global module object.
    Supported units are: [m], [cm], [km], [mi], [nmi], [ft], [in].

    Args:
        xyz: Dataclass 'CoordXYZ' instance:
            CoordXYZ(x: float, y: float, z: float, unit: str).
        unit: String of desired unit, acts as key in dict '_conversion'.

    Returns:
        Same CoordXYZ position, but converted to the desired input unit.
    """
    # If not already in meters, convert to meters first
    if xyz.unit != "m":
        xyz.x = xyz.x / _conversion[xyz.unit]
        xyz.y = xyz.y / _conversion[xyz.unit]
        xyz.z = xyz.z / _conversion[xyz.unit]
    xyz.x = xyz.x * _conversion[unit]
    xyz.y = xyz.y * _conversion[unit]
    xyz.z = xyz.z * _conversion[unit]
    xyz.unit = unit
    return xyz


def _convert_xyz_to_utm(
    theta: float, x: float, y: float, ref_easting: float, ref_northing: float
) -> Tuple[float, float]:
    """Simple function that converts xyz to utm easting and northing.

    Args:
        theta: Used to rotate xyz to utm.
        x: Cartesian x value.
        y: Cartesian y value.
        ref_easting: Used to translate x to utm easting.
        ref_northing: Used to translate y to utm northing

    Returns:
        A tuple with easting and northing respectively.
    """
    easting = np.cos(theta) * x - np.sin(theta) * y + ref_easting
    northing = np.sin(theta) * x + np.cos(theta) * y + ref_northing
    return (easting, northing)


# *---------------------------------*
# | Functions used by other modules |
# *---------------------------------*


def distance_xy(P0: Union[CoordXYZ, Point], P1: Union[CoordXYZ, Point]) -> float:
    """Finds and returns the distance between two points.

    Args:
        P0: Can be either dataclass Point or CoordXYZ (both have x and y attributes)
        P1: P0: Can be either dataclass Point or CoordXYZ (both have x and y attributes)

    Returns:
        Returns the found distance as a float.
    """
    return np.sqrt(((P1.x - P0.x) ** 2) + ((P1.y - P0.y) ** 2))


def convert_tag_xyz_to_latlong(pos: CoordXYZ, station_data: StationData) -> LatLong:
    """Simple function to rotate tag xyz back to utm and convert this to latlong.

    Args:
        pos: XYZ-position of tag.
        station_data: Instance of dataclass StationData, containing attributes:
            'theta': used to rotate back to utm.
            'utm_A.easting' & 'utm_A.northing': used to translate back to utm.
            'utm_zone_num' & 'utm_zone_letter': used to convert utm to latlong.

    Returns:
        Returns instance of dataclass LatLong with latitude and longitude values.

    """
    A = station_data.utm_A
    zone_number = station_data.utm_zone_num
    zone_letter = station_data.utm_zone_let
    theta = station_data.theta
    easting, northing = _convert_xyz_to_utm(theta, pos.x, pos.y, A.easting, A.northing)
    lat, lon = utm.to_latlon(easting, northing, zone_number, zone_letter)
    return LatLong(lat, lon)


def resolve_position_based_on_order_of_arrival(
    tstamps: Timestamps, station_data: StationData, positions: np.array
) -> Tuple[CoordXYZ, CoordXYZ, Optional[CoordXYZ]]:
    """Simple algorithm to resolve ambiguity of position candidates.

    Finds and sorts time of arrival and position for each station. Based on this order,
    and the distance to the candidates, a position candidate can be concluded in most
    cases.

    Args:
        tstamps: Instance of dataclass Timestamps with attributes 'sec_i' and 'msec_i'
            (where i = a, b, c)
        station_data: Instance of dataclass StationData containing position of stations.
        positions: Position candidates found thus far by TDOA hyperbola algorithm.

    Returns:
        Returns a Tuple of the two position candidates, and the position chosen as a
        solution. If no candidate can be chosen, both candidates are returned and
        position solution is returned as None.
    """
    if positions.size == 1:
        return (positions[0], positions[0], positions[0])
    # Extract UTC timestamp and millisecond of arrival, and positions of stations
    T_A = tstamps.sec_a + (tstamps.msec_a / 1000)
    T_B = tstamps.sec_b + (tstamps.msec_b / 1000)
    T_C = tstamps.sec_c + (tstamps.msec_c / 1000)
    P_A, P_B, P_C = (station_data.xyz_A, station_data.xyz_B, station_data.xyz_C)

    # Map time of arrival to position of station
    mapToaPos = {T_A: P_A, T_B: P_B, T_C: P_C}

    # Find the two first arrivals
    T = np.array([T_A, T_B, T_C])
    T.sort()
    T_1st, T_2nd, T_3rd = T

    # Extract positions from stations and candidate positions of tag
    P0, P1 = positions
    P_1st, P_2nd, P_3rd = mapToaPos[T_1st], mapToaPos[T_2nd], mapToaPos[T_3rd]

    # Find distance between position candidates and stations
    d_1st_P0 = distance_xy(P0, P_1st)
    d_1st_P1 = distance_xy(P1, P_1st)
    d_2nd_P0 = distance_xy(P0, P_2nd)
    d_2nd_P1 = distance_xy(P1, P_2nd)
    d_3rd_P0 = distance_xy(P0, P_3rd)
    d_3rd_P1 = distance_xy(P1, P_3rd)

    # Resolve position ambiguity based on order of receiving the message
    if d_1st_P0 < d_2nd_P0 and d_2nd_P1 < d_1st_P1:
        position = P0
    elif d_1st_P1 < d_2nd_P1 and d_2nd_P0 < d_1st_P0:
        position = P1
    elif d_2nd_P0 < d_3rd_P0 and d_3rd_P1 < d_2nd_P1:
        position = P0
    elif d_2nd_P1 < d_3rd_P1 and d_3rd_P0 < d_2nd_P0:
        position = P1
    else:
        position = None  # Further checks needed

    return (P0, P1, position)


def verify_position_within_sea_cage(
    P0: CoordXYZ,
    P1: CoordXYZ,
    position: Optional[CoordXYZ],
    cageCircle: Circle,
    rThresh: float = 1.1,
) -> Optional[CoordXYZ]:
    """Simple function that checks if position candidate is within cage cirumreference.

    Checks whether solution (position != None), or candidates (position = None), are
    within cage cirumreference based on distance from cage center. If both canidates
    are within the cage, choose the one closest to the center.

    Args:
        P0: XYZ-point candidate 0.
        P1: XYZ-point candidate 1.
        position: XYZ-point chosen solution (None if none is chosen so far)
        cageCircle: Instance of dataclass Circle. Has attributes 'radius' and 'center'.
        rThresh: How much more than the cage radius are we accepting (default=1.1)

    Returns:
        If a valid position is chosen, that position is returned (CoordXYZ).
        If not, None is returned.
    """
    rmax = rThresh * cageCircle.radius

    # If only 1 valid position has been found, check if it is valid
    if position is not None:
        d_cageCenter = distance_xy(position, cageCircle.center)
        if d_cageCenter >= rmax:
            position = None
    else:
        d_P0_cageCenter = distance_xy(P0, cageCircle.center)
        d_P1_cageCenter = distance_xy(P1, cageCircle.center)
        # Check if at least one of the positions are within the cage
        if (d_P0_cageCenter < rmax) or (d_P1_cageCenter < rmax):
            # Accept the candidate closest to the center as the solution
            if d_P0_cageCenter < d_P1_cageCenter:
                position = P0
            else:
                position = P1
        else:
            position = None
    return position


def tdoa_hyperbola_algorithm(
    depth: float, tstamps: Timestamps, station_data: StationData
) -> CoordXYZ:
    """Calculates x-y-z coordinates based on station data, depth and timestamps.

    Calculates x-y-z coordinates with algorithm from Bertrand T. Fang's 1989 paper,
    | --> 'Simple Solutions for Hyperbolic and Related Position Fixes'.
    Algorithm is a 'Time Difference of Arrival' (TDOA) technique for positoning, where 3
    stations (A, B, C) with known positions, are used to measure difference in times of
    arrival of signal, leading to a hyperbolic solution for position fix. In this case,
    providing a 2D solution, while the third dimension z is provided by depth argument.

    Args:
        depth: Depth of signal, defining z-value of position [m units]
        timestamps: Dataclass 'Timestamps' with member variables containing
            second and millisecond time arrival of signal in station A, B and C.
        station_data: Dataclass 'StationData' with member variables containing
            integer id, latitude/longitude position, depth, and x-y-z position
            for station A, B, and C [m units].

            XY position of A is always (0, 0)
            XY position of B is always (b, 0)
            XY position of C is always (cx, cy)

    Returns:
        An instance of dataclass 'CoordXYZ' with member variables x, y, and z.
        Coordinates describe 3D-position of signal in relation to coordinate
        system defined by station data. The position is returned in unit cm.
    """
    # Extract values from input matrixes in algorithm/paper naming convention
    sec_a, msec_a = tstamps.sec_a, tstamps.msec_a
    sec_b, msec_b = tstamps.sec_b, tstamps.msec_b
    sec_c, msec_c = tstamps.sec_c, tstamps.msec_c

    # Enforce that coordinate data is in meters
    # station_data.xyz_B = _convert_xyz_unit(station_data.xyz_B, "m")
    # station_data.xyz_C = _convert_xyz_unit(station_data.xyz_C, "m")

    # Coordinates of stations
    b = station_data.xyz_B.x
    cx = station_data.xyz_C.x
    cy = station_data.xyz_C.y
    c = np.sqrt(cx ** 2 + cy ** 2)
    z = depth - station_data.depth

    # Main equations:
    # | sqrt(x² + y² + z²) - sqrt((x-b)² + y² + z²) = V * T_ab = R_ab  (1)
    # | sqrt(x² + y² + z²) - sqrt((x-cx)² + (y-cy)² + z²) = V * T_ac = R_ac  (2)

    # Sound speed
    v = 1500

    # Calculate R_ab and R_ac using eq. (1) and (2)
    T_a = sec_a + (msec_a / 1000)
    T_b = sec_b + (msec_b / 1000)
    T_c = sec_c + (msec_c / 1000)
    R_ab = v * (T_a - T_b)
    R_ac = v * (T_a - T_c)

    # create x_candidates and y_candidates vectors
    x_candidates = np.zeros(2)
    y_candidates = np.zeros(2)

    # Transposing, squaring and simplifying equation (1) and (2) gives:
    # | R²_ab - b² + 2b*x = 2R_ab*sqrt(x²+y²+z²)  (3)
    # | R²_ac - c² + 2*cx*x + 2*cy*y = 2R_ac*sqrt(x²+y²+z²)  (4)

    if R_ab == 0:
        # equation (3) with R_ab equal to 0:
        # | ==> x = b/2
        x = b / 2
        x_candidates[0] = x  # equal roots
        x_candidates[1] = x  # equal roots
        if R_ac == 0:
            print("Both R_ab and R_ac are zero")
            # If R_ab and R_ac is 0, position equal distance to all stations, trivial
            # Solve equation (4) for y with R_ab = 0 (x = b/2) and R_ac = 0:
            # | ==> y = (c² - 2*cx*x) / (2*cy)
            y = ((c ** 2) - 2 * cx * x) / (2 * cy)
            positions = np.array([CoordXYZ(x, y, depth)])
            return positions
        else:
            print("R_ab is zero")
            # Solve equation (4) for y with z = depth and R_ab = 0 (x = b/2):
            # | Put equation (4) on quadratic form:
            #   | term = R²_ac - c² + 2*cx*x
            #   | a_2 = 4*cy*(cy²-R²_ac)
            #   | a_1 = 2*cy*term
            #   | a_0 = term² - 4*R²_ac*(x²+z²)
            #   | ==> y²*a_2 + y*a_1 + a_0 = 0
            quad_term = (R_ac ** 2) - (c ** 2) + (2 * cx * x)
            a_2 = 4 * ((cy ** 2) - (R_ac ** 2))
            a_1 = 2 * (2 * cy) * quad_term
            a_0 = (quad_term ** 2) - (4 * (R_ac ** 2) * ((x ** 2) + (z ** 2)))
            poly = np.array([a_2, a_1, a_0])
            y_candidates = np.roots(poly)
    else:
        # Additional equations (equations for g, h, d, e and f given in code):
        # | y = g * x + h  (5)
        # | z = +-sqrt(d*x² + e*x + f)  (8)
        #   | ==> dx² + ex + f-z² = 0
        # | pos_xyz = xi^ + (g * x + h)j^ +- sqrt(d*x² + e*x + f)k^  (13)
        #   | where i^, j^, and k^ are unit vectors in x-, y- and z-direction.

        # Calculate g, h, d, e and f
        b_Rab = b / R_ab
        b_Rab_1 = 1 - (b_Rab ** 2)
        g = (R_ac * b_Rab - cx) / cy  # eq. (6)
        h = ((c ** 2) - (R_ac ** 2) + (R_ac * R_ab * b_Rab_1)) / (2 * cy)  # eq. (7)
        d = -(b_Rab_1 + (g ** 2))  # eq. (10)
        e = b * b_Rab_1 - 2 * g * h  # eq. (11)
        f = ((R_ab ** 2) / 4) * (b_Rab_1 ** 2) - (h ** 2)  # eq. (12)

        # Calculate x and y, where x is found with equation (8) and y with equation (5)
        x_polynomial = np.array([d, e, f - (z ** 2)])
        x_candidates = np.roots(x_polynomial)
        y_candidates = g * x_candidates + h

    # Reject complex solutions if they exist (does not reject complex number with 0j)
    index = np.argwhere(np.iscomplex(x_candidates))
    x_candidates = np.delete(x_candidates, index)
    y_candidates = np.delete(y_candidates, index)

    # Take the real value in case the candidate object has 0j imaginary part
    x_candidates = np.real(x_candidates)
    y_candidates = np.real(y_candidates)
    numOfCandidates = x_candidates.size

    # Pack candidates into array and return
    if numOfCandidates == 1:
        x = x_candidates.item()
        y = y_candidates.item()
        positions = np.array([CoordXYZ(x, y, depth)])
    elif numOfCandidates == 2:
        x_0, x_1 = x_candidates
        y_0, y_1 = y_candidates
        positions = np.array([CoordXYZ(x_0, y_0, depth), CoordXYZ(x_1, y_1, depth)])
    else:
        positions = None
    return positions
