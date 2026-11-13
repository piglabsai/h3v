"""ECEF chord vectors against Cartesian positions and exact radial differences."""

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


class VectorEcefTests(unittest.TestCase):
    def test_cartesian_difference_magnitude_reversal_and_units(self):
        rng = random.Random(20261115)
        for i in range(100):
            origin, destination = [h3v.latlngalt_to_voxel(
                rng.uniform(-90, 90), rng.uniform(-180, 180),
                rng.uniform(-float(R) + 1, h3v.MAX_ALTITUDE),
                (0, 9, 15)[(i + j) % 3], (0, 7, 10)[(i + j) % 3],
            ) for j in range(2)]
            first, second = h3v.voxel_to_ecef(origin), h3v.voxel_to_ecef(destination)
            expected = tuple(b - a for a, b in zip(first, second))
            tolerance = 64 * math.ulp(max(math.hypot(*first), math.hypot(*second)))
            vector = h3v.voxels_to_vector_ecef(origin, destination)
            self.assertEqual(len(vector), 3)
            self.assertTrue(all(type(v) is float and math.isfinite(v) for v in vector))
            for actual, target in zip(vector, expected):
                self.assertAlmostEqual(actual, target, delta=tolerance)
            self.assertTrue(math.isclose(math.hypot(*vector), h3v.voxels_to_line(origin, destination)[0],
                                         rel_tol=3e-15))
            reverse = h3v.voxels_to_vector_ecef(destination, origin)
            for forward, backward in zip(vector, reverse):
                self.assertAlmostEqual(forward, -backward, delta=tolerance)
            self.assertEqual(vector, h3v.voxels_to_vector_ecef(origin, destination, distance_unit='km'))
            self.assertEqual(h3v.voxels_to_vector_ecef(origin, destination, distance_unit='m'),
                             tuple(v * 1000 for v in vector))

    def test_known_axes_poles_and_antipodes(self):
        first_cell, second_cell = h3.get_res0_cells()[:2]
        radial = _pack_radial(1, 0)
        origin, destination = (radial << 64) | first_cell, (radial << 64) | second_cell
        radius = float(3 * R / 2)
        for positions, expected in (
            ({first_cell: (0.0, 0.0), second_cell: (0.0, 90.0)}, (-radius, radius, 0.0)),
            ({first_cell: (0.0, 0.0), second_cell: (0.0, 180.0)}, (-2*radius, 0.0, 0.0)),
            ({first_cell: (90.0, 15.0), second_cell: (-90.0, -45.0)}, (0.0, 0.0, -2*radius)),
            ({first_cell: (90.0, 0.0), second_cell: (0.0, 90.0)}, (0.0, radius, -radius)),
            ({first_cell: (-90.0, 0.0), second_cell: (0.0, 0.0)}, (radius, 0.0, radius)),
        ):
            with patch.object(geometry.h3, 'cell_to_latlng', side_effect=positions.__getitem__):
                vector = h3v.voxels_to_vector_ecef(origin, destination)
                for actual, target in zip(vector, expected):
                    self.assertAlmostEqual(actual, target, delta=4 * math.ulp(radius))

    def test_small_radial_steps_near_center_and_outer_limit(self):
        cell = h3.latlng_to_cell(52, 13, 15)
        latitude, longitude = map(math.radians, h3.cell_to_latlng(cell))
        unit_vector = (math.cos(latitude)*math.cos(longitude),
                       math.cos(latitude)*math.sin(longitude), math.sin(latitude))
        for rr in (0, 10):
            for b in (0, 256 * 7**rr - 2):
                origin, destination = [(_pack_radial(k, rr) << 64) | cell for k in (b, b + 1)]
                step = float(R / 7**rr)
                vector = h3v.voxels_to_vector_ecef(origin, destination)
                self.assertTrue(math.isclose(math.hypot(*vector), step, rel_tol=5e-16))
                for actual, direction in zip(vector, unit_vector):
                    self.assertAlmostEqual(actual, step * direction, delta=4*math.ulp(step))
                self.assertEqual(h3v.voxels_to_vector_ecef(destination, origin), tuple(-v for v in vector))

    def test_coincident_centers_include_distinct_voxels(self):
        origin = h3v.latlngalt_to_voxel(52, 13, -1, 3, 2)
        central_child = h3v.voxel_to_children(origin)[3]
        self.assertNotEqual(origin, central_child)
        for destination in (origin, central_child):
            for unit in ('km', 'm'):
                self.assertEqual(h3v.voxels_to_vector_ecef(origin, destination, distance_unit=unit),
                                 (0.0, 0.0, 0.0))

    def test_invalid_units_and_voxels_at_both_endpoints(self):
        origin = h3v.latlngalt_to_voxel(52, 13, 1, 9, 10)
        for unit in (None, True, 1, [], {}, 'KM', 'degs', ''):
            with self.assertRaises(ValueError):
                h3v.voxels_to_vector_ecef(origin, origin, distance_unit=unit)
        for invalid in (None, True, 0, -1, 1.0, str(origin), 1 << 128,
                        h3v.voxel_to_cell(origin), *h3v.origin_to_directed_edges(origin)):
            for first, second in ((origin, invalid), (invalid, origin)):
                with self.assertRaises(ValueError):
                    h3v.voxels_to_vector_ecef(first, second)


if __name__ == '__main__':
    unittest.main()
