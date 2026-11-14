"""Contract checks for unsigned, radius-based H3V indices."""
from fractions import Fraction
import math
import random
import unittest

from h3.api import basic_int as h3
import h3v
import _h3v_core as core

A = Fraction.from_float(h3v.authalic_earth_radius())
CELL = h3.latlng_to_cell(52, 13, 3)
LIMIT = 255*A


def voxel(height, resolution):
    return h3v.latlngalt_to_voxel(52, 13, height, 3, resolution)


class FormatContractTests(unittest.TestCase):
    def test_radius_bin_roundtrips_all_bases_and_cross_zero_adjacency(self):
        for r in range(11):
            s = 7**r
            step = A/s
            negative, nonnegative = voxel(-step/2, r), voxel(0, r)
            before = h3v.voxel_to_altitude_bounds(negative)
            after = h3v.voxel_to_altitude_bounds(nonnegative)
            self.assertEqual(before.upper_ratio, after.lower_ratio)
            self.assertEqual(before.upper_ratio, (0, 1))
            self.assertFalse(before.contains(0))
            self.assertTrue(after.contains(0))
            self.assertEqual((negative >> 104) & 255, 0)
            self.assertEqual((nonnegative >> 104) & 255, 1)
            for level in range(r):
                shift = 64 + 4*(9-level)
                self.assertEqual((negative >> shift) & 15, 6)
                self.assertEqual((nonnegative >> shift) & 15, 0)
            for source, delta, target in ((negative, 1, nonnegative),
                                          (nonnegative, -1, negative)):
                level, k = core._read_radial(source >> 64)
                self.assertEqual(level, r)
                self.assertEqual(k, s-1 if delta == 1 else s)
                self.assertEqual((core._pack_radial(k+delta, r) << 64) | CELL, target)

            rng = random.Random(r)
            for base in range(256):
                for refinement in {0, s//2, s-1, rng.randrange(s)}:
                    k = base*s + refinement
                    index = voxel((k+Fraction(1, 2))*step-A, r)
                    self.assertEqual(core._read_radial(index >> 64), (r, k))
                    self.assertEqual(core._pack_radial(k, r), index >> 64)
                    bounds = h3v.voxel_to_altitude_bounds(index)
                    self.assertEqual(Fraction(*bounds.lower_ratio), k*step-A)
                    self.assertEqual(Fraction(*bounds.upper_ratio), (k+1)*step-A)
                    self.assertEqual(bounds.lower_inclusive, k != 0)
                    self.assertFalse(bounds.upper_inclusive)
                    self.assertEqual(voxel(Fraction(*bounds.midpoint_ratio), r), index)
                    self.assertEqual(h3v.str_to_int(h3v.int_to_str(index)), index)
                    self.assertGreater(h3v.voxel_volume(index), 0)

    def test_hierarchy_extreme_bases_midpoints_and_volume(self):
        for r in range(10):
            s = 7**r
            for base in (0, 1, 2, 127, 128, 254, 255):
                for j in {0, s//2, s-1}:
                    k = base*s+j
                    parent = voxel((k+Fraction(1, 2))*A/s-A, r)
                    children = h3v.voxel_to_children(parent)
                    bounds = h3v.voxel_to_altitude_bounds(parent)
                    intervals = [h3v.voxel_to_altitude_bounds(c) for c in children]
                    self.assertEqual(intervals[0].lower_ratio, bounds.lower_ratio)
                    self.assertEqual(intervals[0].lower_inclusive, bounds.lower_inclusive)
                    self.assertEqual(intervals[-1].upper_ratio, bounds.upper_ratio)
                    self.assertEqual(intervals[3].midpoint_ratio, bounds.midpoint_ratio)
                    for left, right in zip(intervals, intervals[1:]):
                        self.assertEqual(left.upper_ratio, right.lower_ratio)
                        self.assertFalse(left.upper_inclusive)
                        self.assertTrue(right.lower_inclusive)
                    for position, child in enumerate(children):
                        self.assertEqual(core._read_radial(child >> 64), (r+1, 7*k+position))
                        self.assertEqual(h3v.voxel_to_parent(child, radial_resolution=r), parent)
                        self.assertEqual((child >> 104) & 255, base)
                        self.assertEqual((child >> (64+4*(9-r))) & 15, position)
                        for q in range(r+1):
                            ancestor = h3v.voxel_to_parent(child, radial_resolution=q)
                            self.assertEqual(core._read_radial(ancestor >> 64),
                                             (q, (7*k+position)//7**(r+1-q)))
                    self.assertTrue(math.isclose(math.fsum(map(h3v.voxel_volume, children)),
                                                 h3v.voxel_volume(parent), rel_tol=2e-15))

    def test_unsigned_base_field_separate_from_digits_resolution_and_header(self):
        for base in range(256):
            radial = (0b100 << 60) | (10 << 48) | (base << 40) | 0x0123456012
            index = (radial << 64) | CELL
            self.assertTrue(h3v.is_valid_voxel(index))
            self.assertEqual(index >> 124, 0b100)
            self.assertEqual((index >> 112) & 15, 10)
            self.assertEqual((index >> 104) & 255, base)
            self.assertEqual((index >> 64) & ((1 << 40)-1), 0x0123456012)
            bounds = h3v.voxel_to_altitude_bounds(index)
            self.assertEqual(voxel(Fraction(*bounds.midpoint_ratio), 10), index)
            self.assertEqual(h3v.str_to_int(h3v.int_to_str(index)), index)

    def test_invalid_headers_and_zero_radials_rejected_consistently(self):
        valid = voxel(0, 3)
        indices = [CELL]
        for header in range(16):
            if header != 0b100:
                indices.append((valid & ((1 << 124)-1)) | (header << 124))

        for radial in (0x2000900555555555, 0x2000980555555555,
                       0x3000900555555555, 0x30009ff555555555):
            indices.append((radial << 64) | CELL)
        for index in indices:
            self.assertFalse(h3v.is_valid_voxel(index))
            for operation in (h3v.get_resolution, h3v.voxel_to_cell, h3v.voxel_to_latlngalt,
                              h3v.voxel_to_boundary, h3v.voxel_to_altitude_bounds,
                              h3v.voxel_volume, h3v.voxel_to_parent, h3v.voxel_to_children,
                              h3v.int_to_str,
                              lambda i: h3v.str_to_int(f'{i:032x}'),
                              lambda i: h3v.voxels_to_line(i, valid),
                              lambda i: h3v.voxels_to_line(valid, i)):
                with self.assertRaises(ValueError):
                    operation(index)

    def test_maximum_resolution_and_exact_domain(self):
        self.assertEqual(h3v.MAX_RADIAL_RESOLUTION, 10)
        self.assertEqual(h3v.MAX_ALTITUDE, 255*h3v.authalic_earth_radius())
        for r in range(11):
            step = A/7**r
            tiny = Fraction(1, 10**1000)
            for altitude in (-A+tiny, -tiny, 0, tiny, LIMIT-tiny):
                index = voxel(altitude, r)
                bounds = h3v.voxel_to_altitude_bounds(index)
                self.assertTrue(bounds.contains(altitude))
                self.assertEqual(Fraction(*bounds.upper_ratio)-Fraction(*bounds.lower_ratio), step)
            for invalid in (-A-tiny, -A, LIMIT, LIMIT+tiny):
                with self.assertRaises(ValueError):
                    voxel(invalid, r)
        for k in (-1, 256*7**10):
            with self.assertRaises(ValueError):
                core._pack_radial(k, 10)
        index = voxel(0, 10)
        with self.assertRaises(ValueError):
            h3v.voxel_to_children(index)
        for invalid in (None, -1, 11, True, 10.0):
            with self.assertRaises(ValueError):
                voxel(0, invalid)

        parent = h3v.voxel_to_parent(index, radial_resolution=9)
        self.assertEqual(h3v.voxel_to_altitude_bounds(h3v.voxel_to_children(parent)[3]).midpoint_ratio,
                         h3v.voxel_to_altitude_bounds(parent).midpoint_ratio)


if __name__ == '__main__':
    unittest.main()
