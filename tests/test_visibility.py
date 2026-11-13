"""Visibility caps checked against horizon limits and Cartesian tangency."""

from decimal import Decimal
from fractions import Fraction
import math
import unittest

from h3.api import basic_int as h3

import h3v
from _h3v_core import _pack_radial


R = Fraction.from_float(h3v.authalic_earth_radius())


class VisibilityTests(unittest.TestCase):
    def test_known_horizon_and_units(self):
        origin = h3v.latlngalt_to_voxel(52, 13, 0, 9, 0)

        for target_altitude in (0, R / 2, 3 * R, 1000, 35786):
            theta = math.acos(2 / 3) + math.acos(float(R / (R + target_altitude)))
            arc = float(R + target_altitude) * theta
            for angle_unit in ('degs', 'rads'):
                for distance_unit in ('km', 'm'):
                    actual = h3v.visibility_cap_radius(
                        origin, target_altitude, angle_unit=angle_unit, distance_unit=distance_unit)
                    self.assertEqual(len(actual), 2)
                    self.assertTrue(all(type(value) is float for value in actual))
                    angle = math.degrees(theta) if angle_unit == 'degs' else theta
                    self.assertAlmostEqual(actual[0], angle, delta=1e-12)
                    self.assertTrue(math.isclose(actual[1], arc * (1000 if distance_unit == 'm' else 1),
                                                 rel_tol=3e-15))
        self.assertEqual(h3v.visibility_cap_radius(origin),
                         h3v.visibility_cap_radius(origin, 0, angle_unit='degs', distance_unit='km'))

    def test_cap_boundary_is_tangent_to_earth(self):
        origin = h3v.latlngalt_to_voxel(0, 0, 0, 3, 0)
        observer_radius = 1.5 * float(R)
        for target_altitude in (R / 2, 3 * R):
            theta, _ = h3v.visibility_cap_radius(origin, target_altitude, angle_unit='rads')
            target_radius = float(R + target_altitude)

            def closest_radius(angle):
                target = (target_radius * math.cos(angle), target_radius * math.sin(angle))
                delta = (target[0] - observer_radius, target[1])
                t = max(0.0, min(1.0, -observer_radius * delta[0] / math.fsum(x*x for x in delta)))
                return math.hypot(observer_radius + t*delta[0], t*delta[1])

            self.assertAlmostEqual(closest_radius(theta), float(R), delta=1e-10)
            self.assertGreater(closest_radius(theta - 1e-5), float(R))
            self.assertLess(closest_radius(theta + 1e-5), float(R))

    def test_surface_index_does_not_affect_radius(self):
        expected = None
        for resolution in (0, 5, 15):
            for cell in (h3.latlng_to_cell(52, 13, resolution), *h3.get_pentagons(resolution)):
                origin = (_pack_radial(7**10 + 123456, 10) << 64) | cell
                result = h3v.visibility_cap_radius(origin, 1000)
                if expected is None:
                    expected = result
                self.assertEqual(result, expected)

    def test_near_surface_precision_and_observer_midpoint(self):
        origin = h3v.latlngalt_to_voxel(52, 13, 0, 9, 10)
        altitude = Fraction(*h3v.voxel_to_altitude_bounds(origin).midpoint_ratio)
        self.assertEqual(altitude, R / (2 * 7**10))
        baseline, arc = h3v.visibility_cap_radius(origin, angle_unit='rads')
        expected = math.atan(math.sqrt(float(altitude * (2*R + altitude) / R**2)))
        self.assertTrue(math.isclose(baseline, expected, rel_tol=3e-15))
        self.assertTrue(math.isclose(arc, float(R) * expected, rel_tol=3e-15))

        height = Fraction(1, 10**20)
        angle, _ = h3v.visibility_cap_radius(origin, height, angle_unit='rads')
        self.assertGreater(angle, baseline)
        self.assertAlmostEqual(angle - baseline, math.sqrt(float(2*height/R)), delta=2*math.ulp(baseline))

    def test_target_shell_is_continuous_and_can_exceed_index_domain(self):
        origin = h3v.latlngalt_to_voxel(52, 13, 1000, 9, 10)
        first = h3v.visibility_cap_radius(origin, 1000)
        second = h3v.visibility_cap_radius(origin, Fraction(1000000001, 1000000))
        self.assertGreater(second[0], first[0])
        self.assertGreater(second[1], first[1])
        for altitude in (h3v.MAX_ALTITUDE * 2, 1e300):
            angle, arc = h3v.visibility_cap_radius(origin, altitude)
            self.assertTrue(0 < angle < 180)
            self.assertTrue(math.isfinite(arc) and arc > 0)
        for altitude, unit in ((10**1000, 'km'), (1e308, 'm')):
            with self.assertRaises(ValueError):
                h3v.visibility_cap_radius(origin, altitude, distance_unit=unit)

    def test_invalid_observers_altitudes_and_units(self):
        origin = h3v.latlngalt_to_voxel(52, 13, 0, 9, 10)
        below = h3v.latlngalt_to_voxel(52, 13, -1, 9, 10)
        for invalid in (None, True, 0, -1, 1 << 128, str(origin), below,
                        h3v.voxel_to_cell(origin), *h3v.origin_to_directed_edges(origin)):
            with self.subTest(origin=invalid):
                with self.assertRaises(ValueError):
                    h3v.visibility_cap_radius(invalid)
        for altitude in (None, True, False, '1', [], Decimal('1'), math.inf, math.nan,
                         -1, -Fraction(1, 10**1000)):
            with self.subTest(target_altitude=altitude):
                with self.assertRaises(ValueError):
                    h3v.visibility_cap_radius(origin, altitude)
        for unit in (None, True, 1, [], {}, 'KM', 'degs', ''):
            with self.assertRaises(ValueError):
                h3v.visibility_cap_radius(origin, distance_unit=unit)
        for unit in (None, True, 1, [], {}, 'degrees', 'km', ''):
            with self.assertRaises(ValueError):
                h3v.visibility_cap_radius(origin, angle_unit=unit)


class KilometerDefaultsTests(unittest.TestCase):
    def test_coordinate_bounds_radius_and_volume_defaults(self):
        self.assertEqual(h3v.authalic_earth_radius(), 6371.007180918475)
        self.assertEqual(h3v.RADIAL_BASE_STEP, h3v.authalic_earth_radius())
        self.assertEqual(h3v.MAX_ALTITUDE, 255 * h3v.authalic_earth_radius())
        origin = h3v.latlngalt_to_voxel(52, 13, 1, 9, 10)
        bounds = h3v.voxel_to_altitude_bounds(origin)
        self.assertTrue(bounds.contains(1))
        self.assertLess(abs(h3v.voxel_to_latlngalt(origin)[2] - 1), float(R / (2 * 7**10)))
        self.assertEqual(h3v.voxel_to_boundary(origin)[0][0][2], bounds.lower)
        self.assertEqual(h3v.voxel_to_boundary(origin)[1][0][2], bounds.upper)
        self.assertEqual(h3v.voxel_volume(origin), h3v.voxel_volume(origin, unit='km^3'))
        self.assertEqual(h3v.voxel_volume(origin, unit='m^3'), h3v.voxel_volume(origin) * 1e9)


if __name__ == '__main__':
    unittest.main()
