"""Straight voxel-center lines, checked against independent Cartesian geometry."""
from fractions import Fraction
import math
import random
import unittest
from unittest.mock import patch

from h3.api import basic_int as h3
import h3v
import _h3v_core as core
import h3v_indexing as indexing
import h3v_geometry as geometry


RADIUS = Fraction.from_float(h3v.authalic_earth_radius())


def representative(index):
    surface, _, level, ordinal = core._read_index(index)
    bounds = indexing._bounds_from_fields(level, ordinal)
    radius = float(RADIUS + Fraction(*bounds.midpoint_ratio))
    lat, lng = map(math.radians, h3.cell_to_latlng(surface))
    up = (math.cos(lat)*math.cos(lng), math.cos(lat)*math.sin(lng), math.sin(lat))
    north = (-math.sin(lat)*math.cos(lng), -math.sin(lat)*math.sin(lng), math.cos(lat))
    east = (-math.sin(lng), math.cos(lng), 0.0)
    return tuple(radius*v for v in up), north, east, up


def cartesian_oracle(origin, destination):
    p0, n0, e0, u0 = representative(origin)
    p1, n1, e1, u1 = representative(destination)
    delta = tuple(b-a for a, b in zip(p0, p1))
    def angles(vector, north, east, up):
        n, e, u = (math.fsum(a*b for a, b in zip(vector, axis))
                   for axis in (north, east, up))
        return math.degrees(math.atan2(e, n)) % 360, math.degrees(math.atan2(u, math.hypot(n, e)))
    return (math.hypot(*delta), *angles(delta, n0, e0, u0),
            *angles(tuple(-v for v in delta), n1, e1, u1))


class LineTests(unittest.TestCase):
    def test_boresight_against_cartesian_geometry_and_units(self):
        rng = random.Random(20261113)
        for i in range(60):
            voxels = [h3v.latlngalt_to_voxel(
                rng.uniform(-85, 85), rng.uniform(-180, 180),
                rng.uniform(-h3v.authalic_earth_radius() + 1, h3v.MAX_ALTITUDE),
                (0, 5, 15)[(i + j) % 3], (0, 4, 10)[(i + j) % 3],
            ) for j in range(3)]
            origin, destination, boresight = voxels
            positions = [representative(v)[0] for v in voxels]
            chords = [tuple(b - a for a, b in zip(positions[0], position))
                      for position in positions[1:]]
            cosine = math.fsum(a*b for a, b in zip(*chords)) / (
                math.hypot(*chords[0]) * math.hypot(*chords[1]))
            expected = math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
            for distance_unit in ('km', 'm'):
                for angle_unit in ('degs', 'rads'):
                    units = dict(distance_unit=distance_unit, angle_unit=angle_unit)
                    line = h3v.voxels_to_line(origin, destination, **units)
                    self.assertEqual(line, h3v.voxels_to_line(origin, destination, boresight=None, **units))
                    result = h3v.voxels_to_line(origin, destination, boresight=boresight, **units)
                    self.assertEqual(result[:5], line)
                    self.assertEqual(len(result), 6)
                    self.assertTrue(all(type(value) is float for value in result))
                    target = math.radians(expected) if angle_unit == 'rads' else expected
                    self.assertAlmostEqual(result[-1], target, delta=1e-10)
                    limit = math.pi if angle_unit == 'rads' else 180.0
                    self.assertTrue(0 <= result[-1] <= limit)
                    swapped = h3v.voxels_to_line(origin, boresight, boresight=destination, **units)
                    self.assertEqual(result[-1], swapped[-1])

    def test_boresight_vertical_and_antipodal_chords(self):
        step = RADIUS / 7**10
        for altitude in (-RADIUS + 3*step/2, 0, 120*RADIUS):
            origin = h3v.latlngalt_to_voxel(52, 13, altitude, 3, 10)
            up = h3v.latlngalt_to_voxel(52, 13, altitude + step, 3, 10)
            down = h3v.latlngalt_to_voxel(52, 13, altitude - step, 3, 10)
            for destination, boresight, expected in ((up, up, 0.0), (down, down, 0.0),
                                                     (up, down, 180.0), (down, up, 180.0)):
                result = h3v.voxels_to_line(origin, destination, boresight=boresight)
                self.assertTrue(math.isnan(result[1]))
                self.assertEqual(result[-1], expected)
                radians = h3v.voxels_to_line(origin, destination, boresight=boresight, angle_unit='rads')
                self.assertEqual(radians[-1], math.radians(expected))
        first, second = h3.get_res0_cells()[:2]
        origin = (core._pack_radial(1, 0) << 64) | first
        antipode = (core._pack_radial(1, 0) << 64) | second
        inward = (core._pack_radial(0, 0) << 64) | first
        outward = (core._pack_radial(2, 0) << 64) | first
        for positions in ({first: (0.0, 0.0), second: (0.0, 180.0)},
                          {first: (90.0, 15.0), second: (-90.0, -45.0)}):
            with patch.object(geometry.h3, 'cell_to_latlng', side_effect=positions.__getitem__):
                self.assertEqual(h3v.voxels_to_line(origin, antipode, boresight=inward)[-1], 0.0)
                self.assertEqual(h3v.voxels_to_line(origin, antipode, boresight=outward)[-1], 180.0)

    def test_boresight_small_and_nearly_opposite_angles(self):
        cells = h3.get_res0_cells()[:3]
        origin, destination, boresight = [(core._pack_radial(1, 0) << 64) | c for c in cells]


        for a, b, expected in ((90.0, -90.0, 90.0), (90.0, 180.0, 45.0),
                               (90.0, 90.0 + 1e-8, ((90.0 + 1e-8) - 90.0)/2),
                               (1e-8, -1e-8, 180.0 - 1e-8)):
            positions = dict(zip(cells, ((0.0, 0.0), (0.0, a), (0.0, b))))
            with patch.object(geometry.h3, 'cell_to_latlng', side_effect=positions.__getitem__):
                angle = h3v.voxels_to_line(origin, destination, boresight=boresight)[-1]
                self.assertAlmostEqual(angle, expected, delta=1e-12)
                if 0 < expected < 1e-7:
                    self.assertGreater(angle, 0.0)

    def test_boresight_coincident_centers(self):
        origin = h3v.latlngalt_to_voxel(52, 13, -1000, 3, 2)
        central_child = h3v.voxel_to_children(origin)[3]
        other = h3v.latlngalt_to_voxel(53, 14, 1000, 3, 2)
        for coincident in (origin, central_child):
            for destination, boresight in ((other, coincident), (coincident, other),
                                          (coincident, coincident)):
                for angle_unit in ('degs', 'rads'):
                    result = h3v.voxels_to_line(origin, destination, boresight=boresight, angle_unit=angle_unit)
                    self.assertEqual(len(result), 6)
                    self.assertTrue(math.isnan(result[-1]))

    def test_invalid_boresight_is_rejected_even_for_coincident_destination(self):
        origin = h3v.latlngalt_to_voxel(52, 13, 0, 3, 9)
        invalid_values = (True, False, -1, 0, 1.0, str(origin), [], {}, 1 << 128,
                          h3v.voxel_to_cell(origin), *h3v.origin_to_directed_edges(origin))
        for boresight in invalid_values:
            with self.subTest(boresight=boresight):
                with self.assertRaises(ValueError):
                    h3v.voxels_to_line(origin, origin, boresight=boresight)

    def test_endpoint_radius_matches_exact_altitude_midpoint(self):
        for resolution in range(h3v.MAX_RADIAL_RESOLUTION + 1):
            scale = 7**resolution
            for base in (0, 1, 127, 128, 255):
                for refinement in {0, scale//2, scale-1}:
                    altitude = (base-1)*RADIUS + (refinement+Fraction(1, 2))*RADIUS/scale
                    index = h3v.latlngalt_to_voxel(52, 13, altitude, 3, resolution)
                    bounds = h3v.voxel_to_altitude_bounds(index)
                    expected = RADIUS + Fraction(*bounds.midpoint_ratio)
                    lat, lng, radius = geometry._line_position(index)
                    self.assertEqual(radius, (expected.numerator, expected.denominator))
                    self.assertGreater(radius[0], 0)
                    self.assertEqual((lat, lng), h3.cell_to_latlng(h3v.voxel_to_cell(index)))

    def test_against_cartesian_geometry_and_reversal(self):
        rng = random.Random(20261106)
        for i in range(100):
            origin = h3v.latlngalt_to_voxel(rng.uniform(-85, 85), rng.uniform(-180, 180),
                                          rng.uniform(-h3v.authalic_earth_radius()+1, h3v.MAX_ALTITUDE),
                                          (0, 5, 15)[i % 3], (0, 4, 10)[i % 3])
            destination = h3v.latlngalt_to_voxel(rng.uniform(-85, 85), rng.uniform(-180, 180),
                                               rng.uniform(-h3v.authalic_earth_radius()+1, h3v.MAX_ALTITUDE),
                                               (15, 0, 5)[i % 3], (10, 0, 4)[i % 3])
            expected = cartesian_oracle(origin, destination)
            result = h3v.voxels_to_line(origin, destination)
            self.assertIs(type(result), tuple)
            self.assertEqual(len(result), 5)
            self.assertTrue(all(type(value) is float for value in result))
            self.assertTrue(math.isclose(result[0], expected[0], rel_tol=2e-14))
            for actual, target in zip(result[1:], expected[1:]):
                self.assertAlmostEqual(actual, target, delta=1e-10)
            self.assertTrue(0 <= result[1] < 360 and 0 <= result[3] < 360)
            self.assertTrue(-90 <= result[2] <= 90 and -90 <= result[4] <= 90)
            reverse = h3v.voxels_to_line(destination, origin)
            for actual, target in zip(reverse, (result[0], *result[3:], *result[1:3])):
                self.assertAlmostEqual(actual, target, delta=1e-10)

    def test_known_chord_angles_and_earth_crossing(self):
        first_cell, second_cell = h3.get_res0_cells()[:2]
        radial = indexing._radial_encode(0, 9)
        first, second = (radial << 64) | first_cell, (radial << 64) | second_cell
        radius = float(RADIUS + RADIUS / (2 * 7**9))
        for coordinates, expected in (
            ({first_cell: (0.0, 0.0), second_cell: (0.0, 90.0)},
             (math.sqrt(2)*radius, 90.0, -45.0, 270.0, -45.0)),
            ({first_cell: (0.0, 0.0), second_cell: (60.0, 0.0)},
             (radius, 0.0, -30.0, 180.0, -30.0)),
        ):
            with patch.object(geometry.h3, 'cell_to_latlng', side_effect=coordinates.__getitem__):
                result = h3v.voxels_to_line(first, second)
                for actual, target in zip(result, expected):
                    self.assertAlmostEqual(actual, target, delta=1e-9)

    def test_coincident_positions_even_with_different_indices(self):
        parent = h3v.latlngalt_to_voxel(52, 13, -1000, 3, 2)
        central_child = h3v.voxel_to_children(parent)[3]
        self.assertNotEqual(parent, central_child)
        surface = h3v.latlngalt_to_voxel(52, 13, 0, 3, 9)
        for origin, destination in ((parent, parent), (parent, central_child), (surface, surface)):
            result = h3v.voxels_to_line(origin, destination)
            self.assertEqual(result[0], 0.0)
            self.assertTrue(all(math.isnan(value) for value in result[1:]))

    def test_vertical_lines_with_exact_radial_difference(self):
        step = RADIUS / 7**10
        for base in (-RADIUS, 120*RADIUS):
            origin = h3v.latlngalt_to_voxel(52, 13, base+step/2, 3, 10)
            destination = h3v.latlngalt_to_voxel(52, 13, base+3*step/2, 3, 10)
            for start, end, elevation in ((origin, destination, 90.0),
                                          (destination, origin, -90.0)):
                result = h3v.voxels_to_line(start, end)
                self.assertEqual(result[0], float(step))
                self.assertTrue(math.isnan(result[1]) and math.isnan(result[3]))
                self.assertEqual((result[2], result[4]), (elevation, -elevation))

    def test_exact_antipodes_and_poles(self):
        first_cell, second_cell = h3.get_res0_cells()[:2]
        radial = indexing._radial_encode(0, 9)
        first, second = (radial << 64) | first_cell, (radial << 64) | second_cell
        radius = float(RADIUS + RADIUS / (2 * 7**9))
        for coordinates in ({first_cell: (0.0, 0.0), second_cell: (0.0, 180.0)},
                            {first_cell: (90.0, 15.0), second_cell: (-90.0, -45.0)}):
            with patch.object(geometry.h3, 'cell_to_latlng', side_effect=coordinates.__getitem__):
                result = h3v.voxels_to_line(first, second)
                self.assertEqual(result[0], 2*radius)
                self.assertTrue(math.isnan(result[1]) and math.isnan(result[3]))
                self.assertEqual((result[2], result[4]), (-90.0, -90.0))

        coordinates = {first_cell: (90.0, 15.0), second_cell: (90.0, -45.0)}
        with patch.object(geometry.h3, 'cell_to_latlng', side_effect=coordinates.__getitem__):
            result = h3v.voxels_to_line(first, second)
            self.assertEqual(result[0], 0.0)
            self.assertTrue(all(math.isnan(value) for value in result[1:]))

    def test_near_center_and_close_surface_positions(self):
        step = RADIUS/7**9
        for altitude in (-RADIUS+step/2, 0):
            origin = h3v.latlngalt_to_voxel(52, 13, altitude, 15, 9)
            destination = h3v.latlngalt_to_voxel(52.00001, 13.00001, altitude, 15, 9)
            result = h3v.voxels_to_line(origin, destination)
            self.assertGreater(result[0], 0)
            self.assertTrue(all(math.isfinite(value) for value in result))
            self.assertAlmostEqual(result[2], result[4], delta=1e-10)
            self.assertLess(result[2], 0)

    def test_all_distance_and_angle_unit_combinations(self):
        origin = h3v.latlngalt_to_voxel(52, 13, -1000, 9, 9)
        destination = h3v.latlngalt_to_voxel(-30, -170, 2000, 9, 9)
        expected = cartesian_oracle(origin, destination)
        self.assertEqual(h3v.voxels_to_line(origin, destination),
                         h3v.voxels_to_line(origin, destination, distance_unit='km', angle_unit='degs'))
        for distance_unit in ('m', 'km'):
            for angle_unit in ('degs', 'rads'):
                result = h3v.voxels_to_line(origin, destination, distance_unit=distance_unit, angle_unit=angle_unit)
                target_distance = expected[0] * (1000 if distance_unit == 'm' else 1)
                self.assertTrue(math.isclose(result[0], target_distance, rel_tol=2e-14))
                for actual, angle in zip(result[1:], expected[1:]):
                    target = math.radians(angle) if angle_unit == 'rads' else angle
                    self.assertAlmostEqual(actual, target, delta=1e-10)
                upper_az = math.tau if angle_unit == 'rads' else 360
                upper_el = math.pi/2 if angle_unit == 'rads' else 90
                self.assertTrue(0 <= result[1] < upper_az and 0 <= result[3] < upper_az)
                self.assertTrue(-upper_el <= result[2] <= upper_el)
                self.assertTrue(-upper_el <= result[4] <= upper_el)

    def test_unit_conversion_preserves_undefined_and_vertical_angles(self):
        origin = h3v.latlngalt_to_voxel(52, 13, 0, 3, 9)
        destination = h3v.latlngalt_to_voxel(52, 13, 1000, 3, 9)
        coincident = h3v.voxels_to_line(origin, origin, distance_unit='m', angle_unit='rads')
        self.assertEqual(coincident[0], 0.0)
        self.assertTrue(all(math.isnan(v) for v in coincident[1:]))
        vertical = h3v.voxels_to_line(origin, destination, distance_unit='m', angle_unit='rads')
        self.assertTrue(math.isnan(vertical[1]) and math.isnan(vertical[3]))
        self.assertEqual((vertical[2], vertical[4]), (math.pi/2, -math.pi/2))
        self.assertEqual(vertical[0], h3v.voxels_to_line(origin, destination)[0] * 1000)

    def test_invalid_unit_selectors_are_rejected_even_for_coincident_points(self):
        voxel = h3v.latlngalt_to_voxel(52, 13, 0, 3, 9)
        for unit in (None, True, 1, [], {}, 'KM', 'rads', 'm^2', ''):
            with self.subTest(distance_unit=unit):
                with self.assertRaises(ValueError):
                    h3v.voxels_to_line(voxel, voxel, distance_unit=unit)
        for unit in (None, False, 1.0, [], {}, 'degrees', 'rad', 'km', ''):
            with self.subTest(angle_unit=unit):
                with self.assertRaises(ValueError):
                    h3v.voxels_to_line(voxel, voxel, angle_unit=unit)

    def test_invalid_voxels_at_both_endpoints(self):
        valid = h3v.latlngalt_to_voxel(52, 13, 1000, 3, 9)
        for invalid in (None, True, -1, 0, 1.0, str(valid), 1 << 128,
                        valid & ((1 << 64)-1), valid | 1 << 127, valid | 1 << 116, valid & ~((1 << 64)-1)):
            for args in ((invalid, valid), (valid, invalid)):
                with self.assertRaises(ValueError):
                    h3v.voxels_to_line(*args)


if __name__ == '__main__':
    unittest.main()
