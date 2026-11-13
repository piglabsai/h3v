"""Spherical ECEF conversions, exact radial assignment, and center round trips."""

from decimal import Decimal
from fractions import Fraction
import math
import random
import unittest
from unittest.mock import patch

from h3.api import basic_int as h3

import h3v
import h3v_indexing as indexing
from _h3v_core import _pack_radial, _read_index


R = Fraction.from_float(h3v.authalic_earth_radius())


class EcefTests(unittest.TestCase):
    def test_axes_defaults_and_resolution_overrides(self):
        radius = h3v.authalic_earth_radius()
        for point, lat, lng in (((radius, 0, 0), 0, 0), ((0, radius, 0), 0, 90),
                                ((-radius, 0, 0), 0, 180), ((0, -radius, 0), 0, -90),
                                ((0, 0, radius), 90, 0), ((0, 0, -radius), -90, 0)):
            voxel = h3v.ecef_to_voxel(*point)
            self.assertEqual(h3v.get_resolution(voxel), (15, 10))
            self.assertEqual(voxel, h3v.latlngalt_to_voxel(lat, lng, 0, 15, 10))
            for sr, rr in ((0, 0), (5, 4), (15, 0), (0, 10)):
                actual = h3v.ecef_to_voxel(*point, surface_resolution=sr, radial_resolution=rr)
                self.assertEqual(actual, h3v.latlngalt_to_voxel(lat, lng, 0, sr, rr))
            self.assertEqual(h3v.get_resolution(h3v.ecef_to_voxel(*point, radial_resolution=3)), (15, 3))
            self.assertEqual(h3v.get_resolution(h3v.ecef_to_voxel(*point, surface_resolution=3)), (3, 10))

    def test_center_cartesian_coordinates_and_roundtrips(self):
        rng = random.Random(20261114)
        for sr, rr in ((0, 0), (0, 10), (9, 7), (15, 10)):
            scale = 7**rr
            for base_cell in h3.get_res0_cells():
                cell = h3.cell_to_center_child(base_cell, sr)
                for b in (0, scale, rng.randrange(256 * scale), 256 * scale - 1):
                    voxel = (_pack_radial(b, rr) << 64) | cell
                    result = h3v.voxel_to_ecef(voxel)
                    self.assertEqual(len(result), 3)
                    self.assertTrue(all(type(v) is float and math.isfinite(v) for v in result))
                    expected_radius = float((Fraction(2*b + 1, 2*scale)) * R)
                    self.assertTrue(math.isclose(math.hypot(*result), expected_radius, rel_tol=5e-16))
                    latitude, longitude = h3.cell_to_latlng(cell)
                    phi, lam = math.radians(latitude), math.radians(longitude)
                    expected = (expected_radius*math.cos(phi)*math.cos(lam),
                                expected_radius*math.cos(phi)*math.sin(lam), expected_radius*math.sin(phi))
                    for actual, target in zip(result, expected):
                        self.assertAlmostEqual(actual, target, delta=4*math.ulp(expected_radius))
                    self.assertEqual(h3v.ecef_to_voxel(*result, surface_resolution=sr, radial_resolution=rr), voxel)

    def test_exact_radius_assignment_without_subtraction(self):
        for rr in (0, 5, 10):
            scale = 7**rr

            actual = h3v.ecef_to_voxel(3, 4, 0, 9, rr)
            expected = h3v.latlngalt_to_voxel(0, math.degrees(math.atan2(4, 3)), 5 - R, 9, rr)
            self.assertEqual(actual, expected)
            for radius, bin_number in ((math.nextafter(float(R), 0), scale - 1),
                                       (float(R), scale), (2*float(R), 2*scale)):
                self.assertEqual(_read_index(h3v.ecef_to_voxel(radius, 0, 0, 9, rr))[3], bin_number)
            for tiny in (math.ulp(0.0), 1e-300, 1e-20):
                for point in ((tiny, 0, 0), (tiny, tiny, tiny)):
                    voxel = h3v.ecef_to_voxel(*point, radial_resolution=rr)
                    self.assertEqual(_read_index(voxel)[3], 0)
                    lat = 0 if point[2] == 0 else math.degrees(math.atan2(1, math.sqrt(2)))
                    lng = 0 if point[1] == 0 else 45
                    self.assertEqual(h3v.voxel_to_cell(voxel), h3.latlng_to_cell(lat, lng, 15))

    def test_outer_limit_and_large_finite_inputs(self):
        limit = 256 * float(R)
        last = h3v.ecef_to_voxel(math.nextafter(limit, 0), 0, 0)
        self.assertEqual(_read_index(last)[3], 256 * 7**10 - 1)
        for point in ((0, 0, 0), (-0.0, 0.0, -0.0), (limit, 0, 0),
                      (-limit, 0, 0), (limit, 1, 0), (math.nextafter(limit, math.inf), 0, 0),
                      (1e308, 1e308, 1e308)):
            with self.subTest(point=point):
                with self.assertRaises(ValueError):
                    h3v.ecef_to_voxel(*point)

    def test_numeric_types_and_invalid_coordinates(self):
        for number in (int, float, Fraction):
            self.assertEqual(h3v.ecef_to_voxel(number(3), number(4), number(0)),
                             h3v.ecef_to_voxel(3, 4, 0))
        for invalid in (None, True, False, '1', [], {}, math.inf, math.nan,
                        Decimal('1'), 10**1000, Fraction(10**1000)):
            for axis in range(3):
                point = [3, 4, 0]
                point[axis] = invalid
                with self.assertRaises(ValueError):
                    h3v.ecef_to_voxel(*point)
        for sr, rr in ((-1, 10), (16, 10), (True, 10), (1.0, 10), (None, 10),
                       (15, -1), (15, 11), (15, True), (15, 1.0), (15, None)):
            with self.assertRaises(ValueError):
                h3v.ecef_to_voxel(3, 4, 0, sr, rr)

    def test_voxel_validation_and_exact_pole_output(self):
        voxel = h3v.latlngalt_to_voxel(52, 13, 1, 9, 10)
        for invalid in (None, True, 0, -1, 1 << 128, 1.0, str(voxel),
                        h3v.voxel_to_cell(voxel), *h3v.origin_to_directed_edges(voxel)):
            with self.assertRaises(ValueError):
                h3v.voxel_to_ecef(invalid)
        for latitude in (-90, 90):
            with patch.object(indexing.h3, 'cell_to_latlng', return_value=(latitude, 45)):
                x, y, z = h3v.voxel_to_ecef(voxel)
                self.assertEqual((x, y), (0, 0))
                self.assertEqual(math.copysign(1, z), math.copysign(1, latitude))


if __name__ == '__main__':
    unittest.main()
