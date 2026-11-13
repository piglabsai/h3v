"""Shell great-circle arcs, including small and nearly antipodal separations."""

from fractions import Fraction
import math
import random
import unittest
from unittest.mock import patch

from h3.api import basic_int as h3

import h3v
import h3v_geometry as geometry
from _h3v_core import _pack_radial


R = Fraction.from_float(h3v.authalic_earth_radius())


class GreatCircleTests(unittest.TestCase):
    def test_against_h3_angles_shell_arc_and_units(self):
        rng = random.Random(20261116)
        for sr, rr in ((0, 0), (5, 4), (15, 10)):
            scale = 7**rr
            for b in (0, scale, 256 * scale - 1):
                radial = _pack_radial(b, rr)
                radius = float(Fraction(2*b + 1, 2*scale) * R)
                for _ in range(15):
                    cells = [h3.latlng_to_cell(rng.uniform(-90, 90), rng.uniform(-180, 180), sr)
                             for _ in range(2)]
                    origin, destination = [(radial << 64) | cell for cell in cells]
                    theta = h3.great_circle_distance(*(h3.cell_to_latlng(c) for c in cells), unit='rads')
                    for angle_unit in ('degs', 'rads'):
                        for distance_unit in ('km', 'm'):
                            units = dict(angle_unit=angle_unit, distance_unit=distance_unit)
                            result = h3v.voxels_to_great_circle(origin, destination, **units)
                            self.assertEqual(len(result), 2)
                            self.assertTrue(all(type(v) is float for v in result))
                            expected_angle = math.degrees(theta) if angle_unit == 'degs' else theta
                            expected_distance = radius * theta * (1000 if distance_unit == 'm' else 1)
                            self.assertAlmostEqual(result[0], expected_angle, delta=1e-12)
                            self.assertTrue(math.isclose(result[1], expected_distance, rel_tol=2e-14, abs_tol=1e-15))
                            self.assertEqual(result, h3v.voxels_to_great_circle(destination, origin, **units))
                    self.assertEqual(h3v.voxels_to_great_circle(origin, destination),
                                     h3v.voxels_to_great_circle(origin, destination, angle_unit='degs', distance_unit='km'))

    def test_known_angles_poles_antimeridian_and_precision(self):
        first, second = h3.get_res0_cells()[:2]
        origin, destination = [(_pack_radial(1, 0) << 64) | cell for cell in (first, second)]
        radius = float(3*R/2)
        cases = (((0, 0), (0, 90), 90), ((0, 0), (0, 180), 180),
                 ((0, 179), (0, -179), 2), ((90, 45), (-90, -70), 180),
                 ((90, 45), (90, -70), 0), ((52, 13), (52, 13), 0),
                 ((0, 0), (0, 1e-10), 1e-10), ((0, 0), (0, 180-1e-8), 180-1e-8))
        for start, end, expected_angle in cases:
            positions = {first: start, second: end}
            with patch.object(geometry.h3, 'cell_to_latlng', side_effect=positions.__getitem__):
                angle, distance = h3v.voxels_to_great_circle(origin, destination)
                self.assertAlmostEqual(angle, expected_angle, delta=5e-14)
                self.assertTrue(0 <= angle <= 180)
                self.assertTrue(math.isclose(distance, radius*math.radians(expected_angle), rel_tol=2e-15, abs_tol=1e-15))
                if 0 < expected_angle < 1e-8:
                    self.assertGreater(angle, 0)
                if 179 < expected_angle < 180:
                    self.assertLess(angle, 180)
        self.assertEqual(h3v.voxels_to_great_circle(origin, origin), (0.0, 0.0))

    def test_distant_endpoints_and_arc_exceeds_chord(self):
        origin = h3v.latlngalt_to_voxel(80, 0, 0, 9, 7)
        destination = h3v.latlngalt_to_voxel(-80, 140, 0, 9, 7)
        with self.assertRaises(ValueError):
            h3v.grid_distance(origin, destination)
        angle, arc = h3v.voxels_to_great_circle(origin, destination)
        self.assertTrue(0 < angle <= 180)
        self.assertGreater(arc, h3v.voxels_to_line(origin, destination)[0])

    def test_mismatched_resolutions_and_radial_words(self):
        origin = h3v.latlngalt_to_voxel(52, 13, 1, 3, 2)
        central_child = h3v.voxel_to_children(origin)[3]
        self.assertEqual(h3v.voxel_to_altitude_bounds(origin).midpoint_ratio,
                         h3v.voxel_to_altitude_bounds(central_child).midpoint_ratio)
        destinations = (central_child, h3v.voxel_to_parent(origin, surface_resolution=2),
                        h3v.latlngalt_to_voxel(52, 13, 200, 3, 2))
        for destination in destinations:
            with self.assertRaises(ValueError):
                h3v.voxels_to_great_circle(origin, destination)

    def test_invalid_inputs_and_units(self):
        origin = h3v.latlngalt_to_voxel(52, 13, 1, 9, 10)
        for invalid in (None, True, 0, -1, 1.0, str(origin), 1 << 128,
                        h3v.voxel_to_cell(origin), *h3v.origin_to_directed_edges(origin)):
            for first, second in ((invalid, origin), (origin, invalid)):
                with self.assertRaises(ValueError):
                    h3v.voxels_to_great_circle(first, second)
        for unit in (None, True, 1, [], {}, 'KM', 'degs', ''):
            with self.assertRaises(ValueError):
                h3v.voxels_to_great_circle(origin, origin, distance_unit=unit)
        for unit in (None, True, 1, [], {}, 'degrees', 'km', ''):
            with self.assertRaises(ValueError):
                h3v.voxels_to_great_circle(origin, origin, angle_unit=unit)


if __name__ == '__main__':
    unittest.main()
