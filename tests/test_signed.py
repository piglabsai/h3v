"""Signed scalar-core acceptance tests; Fraction is an independent test oracle."""
from fractions import Fraction
import math
import random
import unittest

from h3.api import basic_int as h3
import h3v
from h3v import (
    authalic_earth_radius,
    MAX_ALTITUDE,
    MAX_RADIAL_RESOLUTION,
    RADIAL_BASE_STEP,
    latlngalt_to_voxel,
    voxel_to_latlngalt,
    int_to_str,
    str_to_int,
    is_valid_voxel,
    get_resolution,
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


class SignedRadialTests(unittest.TestCase):
    def test_negative_exact_boundaries_and_neighbors(self):
        for resolution in range(11):
            scale = 7**resolution
            step = RADIUS / scale
            epsilon = step / 10**100
            for ordinal in sorted({0, scale // 2, scale - 1}):
                lower = -RADIUS + ordinal * step
                upper = lower + step
                index = cell_at_height((lower + upper) / 2, resolution)
                bounds = bounds_for_cell(index)
                self.assertEqual(Fraction(*bounds.lower_ratio), lower)
                self.assertEqual(Fraction(*bounds.upper_ratio), upper)
                self.assertEqual(bounds.lower_inclusive, ordinal != 0)
                self.assertFalse(bounds.upper_inclusive)
                self.assertFalse(bounds.contains(upper))
                self.assertEqual(cell_at_height(lower + epsilon, resolution), index)
                self.assertEqual(cell_at_height(upper - epsilon, resolution), index)
                if ordinal:
                    self.assertEqual(cell_at_height(lower, resolution), index)
                    self.assertNotEqual(cell_at_height(lower - epsilon, resolution), index)
                else:
                    with self.assertRaises(ValueError):
                        cell_at_height(lower, resolution)
                if upper:
                    self.assertNotEqual(cell_at_height(upper, resolution), index)

    def test_center_and_zero_are_open_without_clipping(self):
        for resolution in range(11):
            step = RADIUS / 7**resolution
            for height in (-RADIUS + Fraction(1, 10**1000),
                           math.nextafter(-authalic_earth_radius(), math.inf)):
                index = cell_at_height(height, resolution)
                bounds = bounds_for_cell(index)
                self.assertEqual(Fraction(*bounds.lower_ratio), -RADIUS)
                self.assertEqual(Fraction(*bounds.upper_ratio), -RADIUS + step)
                self.assertFalse(bounds.lower_inclusive)
                self.assertFalse(bounds.contains(-RADIUS))
                self.assertTrue(bounds.contains(height))
                self.assertEqual(cell_at_height(Fraction(*bounds.midpoint_ratio), resolution), index)
            near_zero = cell_at_height(-math.ulp(0.0), resolution)
            bounds = bounds_for_cell(near_zero)
            self.assertEqual(Fraction(*bounds.lower_ratio), -step)
            self.assertEqual(bounds.upper_ratio, (0, 1))
            self.assertFalse(bounds.contains(0))
            self.assertNotEqual(near_zero >> 64, 0)

    def test_negative_hierarchy_has_seven_radius_ordered_children(self):
        surface = h3.latlng_to_cell(52, 13, 3)
        for resolution in range(10):
            for height in (-Fraction(1, 1000), -RADIUS/2,
                           -RADIUS + Fraction(1, 10**100)):
                index = cell_at_height(height, resolution, surface=surface)
                bounds = bounds_for_cell(index)
                children = voxel_to_children(index)
                self.assertEqual(len(children), 7)
                intervals = [bounds_for_cell(child) for child in children]
                self.assertEqual(intervals[0].lower_ratio, bounds.lower_ratio)
                self.assertEqual(intervals[-1].upper_ratio, bounds.upper_ratio)
                self.assertEqual(intervals[0].lower_inclusive, bounds.lower_inclusive)
                self.assertEqual(intervals[3].midpoint_ratio, bounds.midpoint_ratio)
                for lower, upper in zip(intervals, intervals[1:]):
                    self.assertEqual(lower.upper_ratio, upper.lower_ratio)
                    self.assertFalse(lower.upper_inclusive)
                    self.assertTrue(upper.lower_inclusive)
                for position, child in enumerate(children):
                    child_radial = (child >> 64)
                    self.assertEqual((child & MASK64), surface)
                    self.assertEqual((child_radial >> 40) & 255, 0)
                    self.assertEqual(voxel_to_parent(child, radial_resolution=resolution), index)
                    self.assertEqual(voxel_to_parent(child, radial_resolution=0), voxel_to_parent(index, radial_resolution=0))
                    shift = 4 * (9 - resolution)
                    self.assertEqual(((child_radial >> shift) & 15), position)
                    midpoint = Fraction(*intervals[position].midpoint_ratio)
                    self.assertEqual(midpoint - Fraction(*bounds.midpoint_ratio),
                                     (position - 3) * RADIUS / 7**(resolution + 1))
                    self.assertEqual(cell_at_height(midpoint, resolution + 1, surface=surface), child)

    def test_serialization_and_invalid_radial_words(self):
        surface = h3.latlng_to_cell(52, 13, 3)
        for height in (-1, -1000, -RADIUS+Fraction(1,10**100)):
            for resolution in range(11):
                index = cell_at_height(height, resolution, surface=surface)
                text = int_to_str(index)
                self.assertEqual(len(text), 32)
                self.assertEqual(str_to_int(text), index)
                self.assertEqual((index >> 104) & 255, 0)
        for bad in (surface,
                    cell_at_height(1, 10) | (7 << 64),
                    cell_at_height(1, 10) | 1 << 127):
            self.assertFalse(is_valid_voxel(bad))
            with self.assertRaises(ValueError):
                h3v.voxel_to_boundary(bad)
            with self.assertRaises(ValueError):
                str_to_int(f'{bad:032x}')


class SignedCoordinateTests(unittest.TestCase):
    def test_negative_coordinate_and_midpoint_round_trips(self):
        rng = random.Random(20261102)
        for surface_resolution in range(16):
            for radial_level in range(11):
                for height in (-Fraction(1, 1000), -1000,
                               -RADIUS+Fraction(1,10**100),
                               rng.uniform(-authalic_earth_radius()+1, -1)):
                    index = latlngalt_to_voxel(rng.uniform(-90,90), rng.uniform(-180,180),
                                             height, surface_resolution, radial_level)
                    self.assertTrue(is_valid_voxel(index))
                    bounds = bounds_for_cell(index)
                    self.assertTrue(bounds.contains(height))
                    latitude, longitude, decoded_height = voxel_to_latlngalt(index)
                    self.assertGreater(decoded_height, -authalic_earth_radius())
                    self.assertLess(decoded_height, 0)
                    self.assertEqual(latlngalt_to_voxel(latitude,longitude,decoded_height,
                                                     surface_resolution,radial_level), index)


    def test_packed_hierarchy_preserves_independent_axes_and_base(self):
        for surface in (h3.latlng_to_cell(52,13,3), h3.get_pentagons(3)[0]):
            for height in (-1000, -RADIUS+Fraction(1,10**100)):
                index = cell_at_height(height, 3, surface=surface)
                self.assertEqual(get_resolution(index), (3,3))
                for refine_surface, refine_radial in ((True,False), (False,True), (True,True)):
                    children = voxel_to_children(index, refine_surface=refine_surface,
                                           refine_radial=refine_radial)
                    self.assertGreater(len(children), 0)
                    for child in children:
                        self.assertEqual((child >> 104) & 255, 0)
                        self.assertEqual(voxel_to_parent(child,3,3), index)
                parent = voxel_to_parent(index,0,0)
                self.assertEqual((parent >> 104) & 255, 0)
                self.assertTrue(bounds_for_cell(parent).contains(height))


if __name__ == '__main__':
    unittest.main()
