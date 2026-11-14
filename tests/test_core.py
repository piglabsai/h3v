"""Acceptance tests for strictly volumetric H3V indices."""
from decimal import Decimal
from dataclasses import FrozenInstanceError
from fractions import Fraction
import math
import random
import unittest
from unittest.mock import patch
import subprocess
import sys

from h3.api import basic_int as h3
import h3v
import _h3v_core as core
import h3v_indexing as indexing
from h3v import (
    authalic_earth_radius,
    RADIAL_BASE_STEP,
    MAX_ALTITUDE,
    MAX_RADIAL_RESOLUTION,
    voxel_to_boundary,
    voxel_to_cell,
    latlngalt_to_voxel,
    voxel_to_latlngalt,
    voxel_to_altitude_bounds,
    int_to_str,
    str_to_int,
    get_resolution,
    voxel_volume,
    is_valid_voxel,
    voxel_to_parent,
    voxel_to_children,
)


MASK64 = (1 << 64) - 1


def cell_at_height(altitude, resolution=None, *, surface=None):
    """Create packed test cells through the public coordinate API."""
    if surface is None:
        return latlngalt_to_voxel(52, 13, altitude, 3, resolution)
    lat, lng = h3.cell_to_latlng(surface)
    return latlngalt_to_voxel(lat, lng, altitude, h3.get_resolution(surface), resolution)


def bounds_for_cell(index):
    """Read exact geometry through the public altitude-bounds API."""
    return h3v.voxel_to_altitude_bounds(index)


RADIUS = Fraction.from_float(authalic_earth_radius())
LIMIT = 255 * RADIUS


class RadialFormatTests(unittest.TestCase):
    def test_public_altitude_bounds_are_exported_and_immutable(self):
        self.assertIn('voxel_to_altitude_bounds', h3v.__all__)
        bounds = voxel_to_altitude_bounds(cell_at_height(1000, 7))
        with self.assertRaises(FrozenInstanceError):
            bounds.lower_inclusive = True

    def test_known_vectors(self):

        for height, resolution, expected in [
            (0, 0, '400001ffffffffff'),
            (0, 10, '400a010000000000'),
            (1, 0, '400001ffffffffff'),
            (RADIUS, 0, '400002ffffffffff'),
            (RADIUS + 1, 0, '400002ffffffffff'),
            (RADIUS / 14, 1, '4001010fffffffff'),
            (RADIUS / 2, 1, '4001013fffffffff'),
            (-RADIUS / 2, 1, '4001003fffffffff'),
            (RADIUS / (2 * 7**10), 10, '400a010000000000'),
            (-RADIUS + RADIUS / (2 * 7**10), 10, '400a000000000000'),
            (RADIUS * Fraction(2 * 1120876 + 1, 2 * 7**9), 9, '400901012345601f'),
            (-RADIUS + RADIUS * Fraction(2 * 1120876 + 1, 2 * 7**9), 9, '400900012345601f'),
            (LIMIT - RADIUS / (2 * 7**10), 10, '400aff6666666666'),
        ]:
            with self.subTest(height=height, resolution=resolution):
                self.assertEqual(f'{cell_at_height(height, resolution) >> 64:016x}', expected)

    def test_zero_is_a_volume_and_requires_resolution(self):
        surface = h3.latlng_to_cell(52, 13, 3)
        for resolution in range(11):
            expected = cell_at_height(0, resolution)
            for value in (0, 0.0, -0.0, Fraction(0)):
                self.assertEqual(cell_at_height(value, resolution), expected)
                for bad in (None, -1, 11, True, 1.0):
                    with self.assertRaises(ValueError):
                        cell_at_height(value, bad)
            self.assertNotEqual(expected >> 64, 0)
            self.assertEqual(get_resolution(expected), (3, resolution))
            bounds = bounds_for_cell(expected)
            self.assertEqual(bounds.lower_ratio, (0, 1))
            self.assertEqual(Fraction(*bounds.upper_ratio), RADIUS / 7**resolution)
            self.assertEqual(Fraction(*bounds.midpoint_ratio), RADIUS / (2 * 7**resolution))
            self.assertTrue(bounds.contains(0))
            self.assertFalse(bounds.contains(Fraction(*bounds.upper_ratio)))
            self.assertGreater(voxel_volume(expected), 0)
            self.assertEqual(voxel_to_latlngalt(expected)[2], bounds.midpoint)
        with self.assertRaises(ValueError):
            latlngalt_to_voxel(52, 13, 0, 3)
        self.assertFalse(is_valid_voxel(surface))

    def test_exact_boundaries_and_rational_neighbors(self):
        for resolution in range(11):
            scale = 7**resolution
            step = RADIUS / scale
            epsilon = step / 10**100
            bins = {-scale, -scale//2, -1, 0, 1, 2, 7, scale,
                    scale+1, 121*scale, 122*scale, 127*scale, 128*scale, 254*scale, 255*scale-1}
            for k in sorted(bins):
                if not -scale <= k < 255*scale:
                    continue
                lower, upper = k*step, (k+1)*step
                index = cell_at_height(lower+epsilon, resolution)
                bounds = bounds_for_cell(index)
                self.assertEqual(Fraction(*bounds.lower_ratio), lower)
                self.assertEqual(Fraction(*bounds.upper_ratio), upper)
                self.assertEqual(bounds.lower_inclusive, k != -scale)
                self.assertFalse(bounds.upper_inclusive)
                self.assertFalse(bounds.contains(upper))
                self.assertEqual(cell_at_height(upper-epsilon, resolution), index)
                if k != -scale:
                    self.assertEqual(cell_at_height(lower, resolution), index)
                    below = cell_at_height(lower-epsilon, resolution)
                    self.assertNotEqual(below, index)
                    self.assertFalse(bounds_for_cell(below).contains(lower))
                if upper < LIMIT:
                    above = cell_at_height(upper, resolution)
                    self.assertNotEqual(above, index)
                    self.assertEqual(above, cell_at_height(upper+epsilon, resolution))
                midpoint = Fraction(*bounds.midpoint_ratio)
                self.assertEqual(cell_at_height(midpoint, resolution), index)

    def test_adjacent_binary_floats_without_snapping(self):
        for resolution in range(11):
            step = RADIUS / 7**resolution
            for boundary in (0.0, -authalic_earth_radius(), float(step), float(-step), MAX_ALTITUDE):
                for value in (math.nextafter(boundary, -math.inf), boundary,
                              math.nextafter(boundary, math.inf)):
                    exact = Fraction(value)
                    if not -RADIUS < exact < LIMIT:
                        with self.assertRaises(ValueError):
                            cell_at_height(value, resolution)
                        continue
                    index = cell_at_height(value, resolution)
                    bounds = bounds_for_cell(index)
                    self.assertTrue(bounds.contains(exact))
                    ordinal = math.floor(exact / step)
                    self.assertEqual(Fraction(*bounds.lower_ratio), ordinal * step)

    def test_all_base_cells_and_exact_upper_limit(self):
        self.assertEqual(len(h3.get_res0_cells()), 122)
        self.assertEqual(RADIAL_BASE_STEP, authalic_earth_radius())
        self.assertEqual(MAX_RADIAL_RESOLUTION, 10)
        self.assertAlmostEqual(authalic_earth_radius() / 7**10, 0.0000225542138770483)

        for base in range(256):
            for resolution in range(11):
                step = RADIUS / 7**resolution
                index = cell_at_height((base-1) * RADIUS + step/2, resolution)
                self.assertEqual((index >> 104) & 255, base)
                self.assertEqual(Fraction(*bounds_for_cell(index).lower_ratio), (base-1)*RADIUS)
        for resolution in range(11):
            epsilon = Fraction(1, 10**100)
            index = cell_at_height(LIMIT-epsilon, resolution)
            self.assertEqual(Fraction(*bounds_for_cell(index).upper_ratio), LIMIT)
            for invalid in (-RADIUS, -RADIUS-epsilon, LIMIT, LIMIT+epsilon,
                            math.nextafter(MAX_ALTITUDE, math.inf)):
                with self.assertRaises(ValueError):
                    cell_at_height(invalid, resolution)

    def test_exact_ratios_and_tiny_inputs(self):
        for resolution in range(11):
            for height in (Fraction('0.1'), 1000, LIMIT-1):
                bounds = bounds_for_cell(cell_at_height(height, resolution))
                for numerator, denominator in (bounds.lower_ratio, bounds.upper_ratio,
                                               bounds.midpoint_ratio):
                    self.assertIs(type(numerator), int)
                    self.assertIs(type(denominator), int)
                    self.assertGreater(denominator, 0)
                    self.assertEqual(math.gcd(numerator, denominator), 1)
                self.assertEqual(Fraction(*bounds.midpoint_ratio) * 2,
                                 Fraction(*bounds.lower_ratio) + Fraction(*bounds.upper_ratio))
                self.assertIs(type(bounds.lower), float)
                self.assertIs(type(bounds.upper), float)
        for height in (math.ulp(0.0), 1e-300, Fraction(1, 10**1000)):
            for signed in (height, -height):
                index = cell_at_height(signed, 9)
                self.assertNotEqual(index >> 64, 0)
                self.assertTrue(bounds_for_cell(index).contains(signed))
                bounds = bounds_for_cell(index)
                self.assertEqual(Fraction(*bounds.upper_ratio) - Fraction(*bounds.lower_ratio),
                                 RADIUS / 7**9)

    def test_rational_components_are_normalized_before_arithmetic(self):
        class RestrictedInteger(int):
            @property
            def numerator(self):
                return self

            @property
            def denominator(self):
                return type(self)(1)

            def __mul__(self, other):
                raise OverflowError("arithmetic must use native Python integers")

            __rmul__ = __mul__

        for height in (0, 1000, -1000):
            value = RestrictedInteger(height)
            numerator, denominator = core._number_ratio(value, 'altitude')
            self.assertIs(type(numerator), int)
            self.assertIs(type(denominator), int)
            index = cell_at_height(value, 9)
            self.assertIs(type(index), int)
            self.assertEqual(index, cell_at_height(height, 9))
            self.assertTrue(bounds_for_cell(index).contains(value))

    def test_numpy_integer_altitudes(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("optional NumPy regression requires NumPy")
        for dtype in (np.int8, np.int16, np.int32, np.int64,
                      np.uint8, np.uint16, np.uint32, np.uint64):
            limits = np.iinfo(dtype)
            values = {0, 1, 100, int(limits.min), int(limits.max)}
            if limits.max >= 1000:
                values.add(1000)
            if limits.min < 0:
                values.add(-1)
                if limits.min <= -1000:
                    values.add(-1000)
            for height in sorted(values):
                value = dtype(height)
                for resolution in (0, 5, 9):
                    with self.subTest(dtype=dtype, height=height, resolution=resolution):
                        if not -RADIUS < height < LIMIT:
                            with self.assertRaises(ValueError):
                                cell_at_height(value, resolution)
                            self.assertFalse(bounds_for_cell(cell_at_height(1000, resolution)).contains(value))
                            continue
                        expected = cell_at_height(height, resolution)
                        index = cell_at_height(value, resolution)
                        self.assertIs(type(index), int)
                        self.assertTrue(is_valid_voxel(index))
                        self.assertEqual(index, expected)
                        self.assertTrue(bounds_for_cell(index).contains(value))
                        packed = latlngalt_to_voxel(52, 13, value, 7, resolution)
                        self.assertIs(type(packed), int)
                        self.assertEqual(packed, latlngalt_to_voxel(52, 13, height, 7, resolution))
                        self.assertEqual(packed >> 64, expected >> 64)
                        self.assertEqual(str_to_int(int_to_str(packed)), packed)

    def test_module_import_without_decimal_or_fractions(self):
        code = """import builtins
original_import = builtins.__import__
def block_optional_numeric_modules(name, *args, **kwargs):
    if name.split('.')[0] in ('decimal', '_decimal', 'fractions'):
        raise ImportError(f'{name} is deliberately unavailable')
    return original_import(name, *args, **kwargs)
builtins.__import__ = block_optional_numeric_modules
import h3v
index = h3v.latlngalt_to_voxel(52, 13, 0.05, 2, 9)
assert h3v.voxel_to_boundary(index)[0][0][2] < 0.05 <= h3v.voxel_to_boundary(index)[1][0][2]
negative = h3v.latlngalt_to_voxel(52, 13, -1, 2, 9)
assert h3v.is_valid_voxel(negative)
assert h3v.latlngalt_to_voxel(*h3v.voxel_to_latlngalt(negative), 2, 9) == negative
"""
        result = subprocess.run([sys.executable, '-I', '-B', '-c', code],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_positive_hierarchy_partitions_and_central_midpoints(self):
        surface = h3.latlng_to_cell(52, 13, 3)
        for resolution in range(10):
            for height in (Fraction(1, 100), RADIUS / 2, RADIUS, RADIUS + 1, LIMIT-1):
                index = cell_at_height(height, resolution, surface=surface)
                children = voxel_to_children(index)
                self.assertEqual(len(children), 7)
                bounds = bounds_for_cell(index)
                intervals = [bounds_for_cell(c) for c in children]
                self.assertEqual(intervals[0].lower_ratio, bounds.lower_ratio)
                self.assertEqual(intervals[-1].upper_ratio, bounds.upper_ratio)
                self.assertEqual(intervals[3].midpoint_ratio, bounds.midpoint_ratio)
                for left, right in zip(intervals, intervals[1:]):
                    self.assertEqual(left.upper_ratio, right.lower_ratio)
                    self.assertFalse(left.upper_inclusive)
                    self.assertTrue(right.lower_inclusive)
                for position, child in enumerate(children):
                    child_radial = (child >> 64)
                    self.assertEqual((child & MASK64), surface)
                    self.assertEqual(voxel_to_parent(child, radial_resolution=resolution), index)
                    self.assertEqual(voxel_to_parent(child, radial_resolution=0), voxel_to_parent(index, radial_resolution=0))
                    shift = 4 * (9 - resolution)
                    self.assertEqual(((child_radial >> shift) & 15), position)
                    midpoint = Fraction(*intervals[position].midpoint_ratio)
                    self.assertEqual(midpoint - Fraction(*bounds.midpoint_ratio),
                                     (position - 3) * RADIUS / 7**(resolution + 1))
        with self.assertRaises(ValueError):
            voxel_to_children(cell_at_height(1, 10, surface=surface))
        with self.assertRaises(ValueError):
            voxel_to_parent(cell_at_height(1, 0, surface=surface), radial_resolution=1)

    def test_numeric_validation(self):
        bounds = bounds_for_cell(cell_at_height(1, 9))
        for value in (True, '1', math.nan, math.inf, None, Decimal('0'), Decimal('0.1'),
                      Decimal('NaN'), Decimal('Infinity')):
            for operation in (
                lambda: cell_at_height(value, 9), lambda: bounds.contains(value),
                lambda: latlngalt_to_voxel(value, 0, 1, 2, 9),
                lambda: latlngalt_to_voxel(0, value, 1, 2, 9),
            ):
                with self.assertRaises(ValueError):
                    operation()
        for resolution in (-1, 11, True, 1.0):
            with self.assertRaises(ValueError):
                cell_at_height(0, resolution)
        with self.assertRaises(ValueError):
            cell_at_height(1)
        for value in (-1, 1 << 64, True, 1.0, '0', None):
            self.assertFalse(is_valid_voxel(value))
            with self.assertRaises(ValueError):
                voxel_to_boundary(value)

    def test_validation_reserved_fields_and_invalid_encoding_rejection(self):
        base = cell_at_height(1, 0)
        for marker in range(16):
            changed = (base & ((1 << 124) - 1)) | marker << 124
            self.assertEqual(is_valid_voxel(changed), marker == 4)
        for bit in (*range(116, 124), 127):
            self.assertFalse(is_valid_voxel(base | 1 << bit))
        for resolution in range(11, 16):
            self.assertFalse(is_valid_voxel(base | resolution << 112))
        for raw_base in range(256):
            changed = (base & ~(255 << 104)) | raw_base << 104
            self.assertEqual(is_valid_voxel(changed), True)
        for resolution in range(11):
            index = cell_at_height(1, resolution)
            for level in range(10):
                shift = 64 + 4 * (9 - level)
                for digit in range(16):
                    changed = (index & ~(15 << shift)) | digit << shift
                    expected = 0 <= digit <= 6 if level < resolution else digit == 15
                    self.assertEqual(is_valid_voxel(changed), expected)
        surface = h3.latlng_to_cell(52, 13, 3)
        for invalid_radial in (0x100000ffffffffff, 0x100120000000000f, 0x100129999999999f):
            packed = (invalid_radial << 64) | surface
            self.assertFalse(is_valid_voxel(packed))
            with self.assertRaises(ValueError):
                voxel_to_latlngalt(packed)


class ConversionTests(unittest.TestCase):
    def test_surface_constructor_is_removed(self):
        self.assertNotIn('cell_to_voxel', h3v.__all__)
        self.assertFalse(hasattr(h3v, 'cell_to_voxel'))

    def test_voxel_to_cell_preserves_surface_at_all_radial_levels(self):
        for surface_resolution in range(16):
            for lat, lng in ((52, 13), (90, 0), (0, -180)):
                surface = h3.latlng_to_cell(lat, lng, surface_resolution)
                for radial_resolution in range(11):
                    for altitude in (0, 1000, -1000, -RADIUS + Fraction(1, 100), LIMIT-1):
                        voxel = latlngalt_to_voxel(lat, lng, altitude,
                                                  surface_resolution, radial_resolution)
                        cell = voxel_to_cell(voxel)
                        self.assertIs(type(cell), int)
                        self.assertEqual(cell, surface)

    def test_cell_and_voxel_conversion_validation(self):
        surface = h3.latlng_to_cell(52, 13, 3)
        volume = latlngalt_to_voxel(52, 13, 1000, 3, 9)
        for bad in (0, -1, True, False, float(volume), str(volume), None,
                    1 << 128, volume | 1 << 127, volume | 1 << 116,
                    volume & ~MASK64, surface, surface | 1 << 63):
            self.assertFalse(is_valid_voxel(bad))
            with self.assertRaises(ValueError):
                voxel_to_cell(bad)

    def test_authalic_radius_matches_h3_distance_scale(self):
        radius = authalic_earth_radius()
        self.assertIs(type(radius), float)

        self.assertEqual(radius, 6371.007180918475)
        self.assertEqual(radius, authalic_earth_radius(unit='km'))
        self.assertEqual(authalic_earth_radius('m'), radius * 1000.0)
        self.assertNotIn('authalic_earth_radius_km', h3v.__all__)
        self.assertFalse(hasattr(h3v, 'authalic_earth_radius_km'))
        self.assertNotIn('AER', h3v.__all__)
        self.assertFalse(hasattr(h3v, 'AER'))
        for endpoint in ((0, 90), (0, math.degrees(1)), (45, 90)):
            angle = h3.great_circle_distance((0, 0), endpoint, unit='rads')
            for unit in ('km', 'm'):
                distance = h3.great_circle_distance((0, 0), endpoint, unit=unit)
                self.assertAlmostEqual(distance, authalic_earth_radius(unit) * angle,
                                       delta=4 * math.ulp(distance))
        for unit in (None, True, 1, [], {}, 'KM', 'degs', ''):
            with self.subTest(unit=unit):
                with self.assertRaises(ValueError):
                    authalic_earth_radius(unit)

    def test_low_half_is_original_h3_at_every_resolution(self):
        for surface_resolution in range(16):
            for lat, lng in ((0, 0), (52, 13), (90, 0), (-90, 0), (20, -180)):
                expected = h3.latlng_to_cell(lat, lng, surface_resolution)
                for radial_resolution in range(11):
                    index = latlngalt_to_voxel(lat, lng, 0, surface_resolution, radial_resolution)
                    self.assertIs(type(index), int)
                    self.assertEqual(index & MASK64, expected)
                    self.assertNotEqual(index >> 64, 0)
                    self.assertEqual(get_resolution(index), (surface_resolution, radial_resolution))
                    self.assertFalse(is_valid_voxel(expected))
                    self.assertEqual(str_to_int(int_to_str(index)), index)

    def test_latlng_passed_unchanged_to_h3(self):
        with patch.object(indexing.h3, 'latlng_to_cell', wraps=h3.latlng_to_cell) as encode:
            index = latlngalt_to_voxel(52.125, -13.75, 1000, 7, 9)
            encode.assert_called_once_with(52.125, -13.75, 7)
        self.assertEqual((index & MASK64), h3.latlng_to_cell(52.125, -13.75, 7))

    def test_packed_hex_and_integer_order(self):
        surface = h3.latlng_to_cell(52, 13, 3)
        index = cell_at_height(Fraction('123456.78901'), 9)
        self.assertIs(type(index), int)
        self.assertEqual(index & MASK64, surface)
        self.assertEqual(int_to_str(index), f'{index:032x}')
        self.assertEqual((index >> 104) & 255, 20)
        restored = str_to_int(int_to_str(index))
        self.assertIs(type(restored), int)
        self.assertEqual(restored, index)
        self.assertEqual(get_resolution(index), (3, 9))
        ordered = [cell_at_height(h, 8) for h in (0, 1, 2, 100)]
        self.assertEqual(sorted(ordered), ordered)
        self.assertLess(cell_at_height(1000, 0), ordered[1])
        cells = [cell_at_height(1000, 9, surface=s) for s in h3.get_res0_cells()]
        self.assertEqual([c & MASK64 for c in sorted(cells)], sorted(h3.get_res0_cells()))

    def test_packed_index_and_string_validation(self):
        surface = h3.latlng_to_cell(52, 13, 3)
        index = cell_at_height(1, 9)
        for bad in ('', '0x'+int_to_str(index), int_to_str(index)[1:],
                    int_to_str(index).upper(), int_to_str(index)+'0',
                    int_to_str(index)+'\n', '0'*32, f'{surface:x}',
                    f'{index & ~MASK64:032x}', None, index):
            with self.assertRaises(ValueError):
                str_to_int(bad)
        invalid_indices = (-1, 1 << 128, True, False, 1.0, 0, None, '0',
                           (1, 2), index & ~MASK64, index | 1 << 127,
                           index | 1 << 63, index | 1 << 118)
        for bad in invalid_indices:
            self.assertFalse(is_valid_voxel(bad))
            for operation in (int_to_str, get_resolution,
                              voxel_volume, voxel_to_latlngalt, voxel_to_boundary,
                              voxel_to_altitude_bounds,
                              voxel_to_parent, voxel_to_children):
                with self.assertRaises(ValueError):
                    operation(bad)

    def test_independent_resolutions_and_volume_roundtrips(self):
        rng = random.Random(20261030)
        for surface_resolution in range(16):
            for radial_resolution in range(MAX_RADIAL_RESOLUTION + 1):
                for lat, lng in ((90, 0), (-90, 0), (0, 180), (0, -180),
                                 (rng.uniform(-89, 89), rng.uniform(-180, 180))):
                    height = rng.uniform(1, MAX_ALTITUDE)
                    index = latlngalt_to_voxel(lat, lng, height, surface_resolution, radial_resolution)
                    self.assertIs(type(index), int)
                    self.assertEqual(get_resolution(index), (surface_resolution, radial_resolution))
                    surface, radial = (index & MASK64, index >> 64)
                    self.assertEqual(surface, h3.latlng_to_cell(lat, lng, surface_resolution))
                    self.assertNotEqual(radial, 0)
                    self.assertTrue(bounds_for_cell(index).contains(height))
                    self.assertLessEqual(abs(voxel_to_latlngalt(index)[2]-height),
                                         RADIAL_BASE_STEP/7**radial_resolution/2+1e-6)
                    restored = latlngalt_to_voxel(*voxel_to_latlngalt(index),
                                               surface_resolution, radial_resolution)
                    self.assertIs(type(restored), int)
                    self.assertEqual(restored, index)
        self.assertEqual((latlngalt_to_voxel(52, 13, 1234, 2, 8) >> 64),
                         (latlngalt_to_voxel(52, 13, 1234, 15, 8) >> 64))


    def test_coordinate_validation(self):
        for lat, lng, height in ((91,0,0),(0,181,0),(0,0,-authalic_earth_radius())):
            with self.assertRaises(ValueError):
                latlngalt_to_voxel(lat,lng,height,0,0)
        for sr, rr in ((16,0),(0,11),(True,0),(0,False)):
            with self.assertRaises(ValueError):
                latlngalt_to_voxel(0,0,0,sr,rr)

    def test_surface_and_volume_hierarchy(self):
        surface = latlngalt_to_voxel(20,-25,0,3,4)
        self.assertEqual(voxel_to_parent(surface), surface)
        for child in voxel_to_children(surface, refine_surface=True, refine_radial=False):
            self.assertEqual(child >> 64, surface >> 64)
            self.assertEqual(voxel_to_parent(child,3), surface)
        volume = latlngalt_to_voxel(20,-25,800000,3,4)
        for angular, radial in ((True,False),(False,True),(True,True)):
            for child in voxel_to_children(volume,refine_surface=angular,refine_radial=radial):
                self.assertIs(type(child), int)
                parent = voxel_to_parent(child,3,4)
                self.assertIs(type(parent), int)
                self.assertEqual(parent,volume)
        for index, options in ((surface,dict(refine_surface=False,refine_radial=False)),
                               (latlngalt_to_voxel(0,0,0,15,4),dict(refine_surface=True,refine_radial=False)),
                               (latlngalt_to_voxel(0,0,1,0,10),dict())):
            with self.assertRaises(ValueError):
                voxel_to_children(index,**options)
        for sr, rr in ((4,None),(3,5),(True,None),(None,False)):
            with self.assertRaises(ValueError):
                voxel_to_parent(volume,sr,rr)
        for angular, radial in ((1,False),(False,0),(None,True)):
            with self.assertRaises(ValueError):
                voxel_to_children(volume,refine_surface=angular,refine_radial=radial)


    def test_supported_geometry_number_types(self):
        expected = latlngalt_to_voxel(52,13,1000,3,9)
        for number in (int,float,Fraction):
            self.assertEqual(latlngalt_to_voxel(number(52),number(13),number(1000),3,9), expected)
        for bad in (True,'52',math.nan,math.inf,Decimal('NaN'),Decimal('sNaN'),None):
            with self.assertRaises(ValueError):
                latlngalt_to_voxel(bad,13,1,3,9)
        for bad in (10**1000,Decimal('1e1000'),Fraction(10**1000)):
            with self.assertRaises(ValueError):
                latlngalt_to_voxel(bad,0,0,3)


class BoundaryTests(unittest.TestCase):
    def test_zero_voxel_base_cell_rings_match_h3(self):
        for surface in h3.get_res0_cells():
            index = cell_at_height(0, 9, surface=surface)
            rings = voxel_to_boundary(index)
            self.assertIs(type(rings), tuple)
            bounds = bounds_for_cell(index)
            for ring, altitude in zip(rings, (bounds.lower, bounds.upper)):
                expected = tuple((lat, lng, altitude) for lat, lng in h3.cell_to_boundary(surface))
                self.assertEqual(ring, expected)
                self.assertNotEqual(ring[0], ring[-1])
                self.assertIs(type(ring), tuple)
                for point in ring:
                    self.assertIs(type(point), tuple)
                    self.assertTrue(all(type(coordinate) is float for coordinate in point))

    def test_signed_volume_rings_match_h3_and_radial_bounds(self):
        for surface_resolution in range(16):
            surfaces = (h3.latlng_to_cell(52, 13, surface_resolution),
                        h3.latlng_to_cell(0, 180, surface_resolution),
                        h3.latlng_to_cell(90, 0, surface_resolution),
                        *h3.get_pentagons(surface_resolution))
            for surface in surfaces:
                boundary = h3.cell_to_boundary(surface)
                for radial_resolution in range(11):
                    for height in (0, 1000, -1000, LIMIT-1):
                        index = cell_at_height(height, radial_resolution, surface=surface)
                        bounds = bounds_for_cell(index)
                        lower, upper = voxel_to_boundary(index)
                        self.assertEqual(tuple(point[:2] for point in lower), boundary)
                        self.assertEqual(tuple(point[:2] for point in upper), boundary)
                        self.assertTrue(all(point[2] == bounds.lower for point in lower))
                        self.assertTrue(all(point[2] == bounds.upper for point in upper))
                        self.assertEqual(len(lower), len(upper))
                        self.assertLess(lower[0][2], upper[0][2])

    def test_additional_face_crossing_points_are_preserved(self):
        surface = 0x81017ffffffffff
        boundary = h3.cell_to_boundary(surface)
        self.assertGreater(len(boundary), len(h3.cell_to_vertexes(surface)))
        index = cell_at_height(1000, 9, surface=surface)
        for ring in voxel_to_boundary(index):
            self.assertEqual(tuple(point[:2] for point in ring), boundary)

    def test_geometric_boundaries_include_unowned_endpoints(self):
        for resolution in range(11):
            index = latlngalt_to_voxel(52, 13, -RADIUS + RADIUS / (2 * 7**resolution),
                                     3, resolution)
            bounds = bounds_for_cell(index)
            lower, upper = voxel_to_boundary(index)
            self.assertTrue(all(point[2] == -authalic_earth_radius() for point in lower))
            self.assertFalse(bounds.lower_inclusive)
            self.assertFalse(bounds.upper_inclusive)
            self.assertEqual(upper[0][2], bounds.upper)
        index = latlngalt_to_voxel(52, 13, 1, 3, 0)
        lower, _ = voxel_to_boundary(index)
        self.assertTrue(all(point[2] == 0.0 for point in lower))
        self.assertTrue(bounds_for_cell(index).lower_inclusive)

    def test_radial_children_share_boundary_rings(self):
        for height in (1000, -1000):
            parent = latlngalt_to_voxel(52, 13, height, 3, 4)
            children = voxel_to_children(parent)
            boundaries = [voxel_to_boundary(child) for child in children]
            self.assertEqual(boundaries[0][0], voxel_to_boundary(parent)[0])
            self.assertEqual(boundaries[-1][1], voxel_to_boundary(parent)[1])
            for inner, outer in zip(boundaries, boundaries[1:]):
                self.assertEqual(inner[1], outer[0])


class VolumeTests(unittest.TestCase):
    def test_exact_radial_volume_integral_for_hexagon_and_pentagon(self):
        radius = Fraction.from_float(authalic_earth_radius())
        surfaces = (h3.latlng_to_cell(52, 13, 3), h3.get_pentagons(3)[0])
        heights = (Fraction(1, 20), 800_000, MAX_ALTITUDE-1,
                   Fraction(-1, 20), -800, -radius + Fraction(1, 100))
        for surface in surfaces:
            for resolution in range(MAX_RADIAL_RESOLUTION + 1):
                for height in heights:
                    with self.subTest(surface=surface, resolution=resolution, height=height):
                        index = cell_at_height(height, resolution, surface=surface)
                        bounds = bounds_for_cell(index)
                        r_min = radius + Fraction(*bounds.lower_ratio)
                        r_max = radius + Fraction(*bounds.upper_ratio)
                        expected = h3.cell_area(surface, unit='rads^2') * float(
                            (r_max**3 - r_min**3) / 3
                        )
                        for unit, divisor in (('km^3', 1), ('m^3', 1e-9)):
                            actual = voxel_volume(index, unit=unit)
                            self.assertIs(type(actual), float)
                            self.assertGreater(actual, 0)
                            self.assertTrue(math.isclose(actual, expected / divisor, rel_tol=2e-15))
                        self.assertEqual(voxel_volume(index), voxel_volume(index, unit='km^3'))

    def test_volume_units_and_validation(self):
        zero = latlngalt_to_voxel(52, 13, 0, 3, 9)
        volume = latlngalt_to_voxel(52, 13, -1000, 3, 9)
        for index in (zero, volume):
            self.assertEqual(voxel_volume(index, 'm^3'), voxel_volume(index, 'km^3') * 1e9)
            for unit in (None, True, 1, [], {}, 'km', 'm^2', 'rads^3', 'KM^3', ''):
                with self.subTest(unit=unit):
                    with self.assertRaises(ValueError):
                        voxel_volume(index, unit=unit)
        self.assertIs(type(voxel_volume(zero, 'km^3')), float)
        self.assertGreater(voxel_volume(zero, 'km^3'), 0.0)

    def test_bare_h3_cells_are_rejected_by_all_voxel_apis(self):
        valid = cell_at_height(0, 9)
        for surface in (h3.latlng_to_cell(52, 13, 3), *h3.get_pentagons(3)):
            self.assertFalse(is_valid_voxel(surface))
            for operation in (voxel_volume, voxel_to_cell, int_to_str, get_resolution,
                              voxel_to_latlngalt, voxel_to_boundary, voxel_to_altitude_bounds,
                              voxel_to_parent, voxel_to_children,
                              lambda index: str_to_int(f'{index:032x}'),
                              lambda index: h3v.voxels_to_line(index, valid),
                              lambda index: h3v.voxels_to_line(valid, index)):
                with self.assertRaises(ValueError):
                    operation(surface)

    def test_radial_children_conserve_volume(self):
        for height in (1, 800_000, MAX_ALTITUDE-1, -1, -800, -authalic_earth_radius() + 0.01):
            for resolution in range(MAX_RADIAL_RESOLUTION):
                index = latlngalt_to_voxel(52, 13, height, 3, resolution)
                children_volume = math.fsum(voxel_volume(child) for child in voxel_to_children(index))
                self.assertTrue(math.isclose(children_volume, voxel_volume(index), rel_tol=2e-15))

    def test_base_cells_fill_radial_volume(self):
        step = Fraction.from_float(authalic_earth_radius()) / 7**8
        actual = math.fsum(voxel_volume(cell_at_height(step / 2, 8, surface=surface))
                           for surface in h3.get_res0_cells())
        radius = Fraction.from_float(authalic_earth_radius())
        expected = 4 * math.pi / 3 * float((radius + step)**3 - radius**3)
        self.assertTrue(math.isclose(actual, expected, rel_tol=1e-13))


if __name__ == '__main__':
    unittest.main()
