"""Horizontal traversal preserves radial cells and follows H3 adjacency."""

import unittest
from unittest.mock import patch

from h3 import H3BaseException, H3FailedError
from h3.api import basic_int as h3

import h3v
import h3v_traversal as traversal
from _h3v_core import _pack_radial


def voxel(cell, bin_number, resolution):
    return (_pack_radial(bin_number, resolution) << 64) | cell


class TraversalTests(unittest.TestCase):
    def test_radial_words_and_resolutions_are_preserved(self):
        for sr in (0, 9, 15):
            cell = h3.latlng_to_cell(52, 13, sr)
            for rr in (0, 7, 10):
                scale = 7**rr
                for b in sorted({0, scale - 1, scale, 256 * scale - 1}):
                    origin = voxel(cell, b, rr)
                    for function, native in ((h3v.grid_ring, h3.grid_ring), (h3v.grid_disk, h3.grid_disk)):
                        self.assertEqual(function(origin), function(origin, 1))
                        self.assertEqual(function(origin, 0), (origin,))
                        for k in (1, 2):
                            results = function(origin, k)
                            self.assertIs(type(results), tuple)
                            self.assertEqual(len(results), len(set(results)))
                            self.assertEqual({h3v.voxel_to_cell(v) for v in results}, set(native(cell, k)))
                            for result in results:
                                self.assertTrue(h3v.is_valid_voxel(result))
                                self.assertEqual(result >> 64, origin >> 64)
                                self.assertEqual(h3v.get_resolution(result), (sr, rr))

    def test_pentagon_rings_and_disks_against_graph_expansion(self):
        cells = [*h3.get_res0_cells(), *h3.get_pentagons(5)]
        for cell in cells:
            origin = voxel(cell, 0, 10)
            seen, frontier = {cell}, {cell}
            for k in range(3):
                self.assertEqual({h3v.voxel_to_cell(v) for v in h3v.grid_ring(origin, k)}, frontier)
                self.assertEqual({h3v.voxel_to_cell(v) for v in h3v.grid_disk(origin, k)}, seen)
                following = {neighbor for current in frontier for neighbor in h3.grid_disk(current, 1)} - seen
                seen |= following
                frontier = following
            if h3.is_pentagon(cell):
                self.assertEqual(len(h3v.grid_ring(origin)), 5)
                self.assertEqual(len(h3v.grid_disk(origin)), 6)

    def test_distances_for_identical_neighboring_and_two_step_voxels(self):
        cell = h3.latlng_to_cell(52, 13, 9)
        for rr in (0, 7, 10):
            for b in (0, 7**rr, 256 * 7**rr - 1):
                origin = voxel(cell, b, rr)
                self.assertEqual(h3v.grid_distance(origin, origin), 0)
                for k in (1, 2):
                    for neighbor in h3v.grid_ring(origin, k):
                        self.assertIs(type(h3v.grid_distance(origin, neighbor)), int)
                        self.assertEqual(h3v.grid_distance(origin, neighbor), k)
                        self.assertEqual(h3v.grid_distance(neighbor, origin), k)

    def test_mismatched_radial_cells_and_surface_resolutions(self):
        cell = h3.latlng_to_cell(52, 13, 9)
        origin = voxel(cell, 7**7, 7)
        for destination in (voxel(cell, 7**7 + 1, 7), voxel(cell, 7**8, 8),
                            voxel(h3.cell_to_parent(cell, 8), 7**7, 7)):
            with self.assertRaises(ValueError):
                h3v.grid_distance(origin, destination)

    def test_h3_distance_failure_is_reported_as_value_error(self):
        origin = h3v.latlngalt_to_voxel(80, 0, 0, 9, 7)
        destination = h3v.latlngalt_to_voxel(-80, 140, 0, 9, 7)
        with self.assertRaises(ValueError) as raised:
            h3v.grid_distance(origin, destination)
        self.assertIsInstance(raised.exception.__cause__, H3BaseException)

    def test_invalid_k_and_h3_neighborhood_failures(self):
        origin = h3v.latlngalt_to_voxel(52, 13, 1, 9, 7)
        for function in (h3v.grid_ring, h3v.grid_disk):
            for k in (-1, True, False, 1.0, None, '1', [], 1 << 31, 10**1000):
                with self.assertRaises(ValueError):
                    function(origin, k)
            with patch.object(traversal.h3, function.__name__, side_effect=H3FailedError()):
                with self.assertRaises(ValueError) as raised:
                    function(origin, 1)
                self.assertIsInstance(raised.exception.__cause__, H3BaseException)

    def test_invalid_voxel_inputs_at_both_endpoints(self):
        origin = h3v.latlngalt_to_voxel(52, 13, 1, 9, 7)
        for invalid in (None, True, 0, -1, 1.0, str(origin), 1 << 128,
                        h3v.voxel_to_cell(origin), *h3v.origin_to_directed_edges(origin)):
            for function in (h3v.grid_ring, h3v.grid_disk):
                with self.assertRaises(ValueError):
                    function(invalid, 0)
            for first, second in ((origin, invalid), (invalid, origin)):
                with self.assertRaises(ValueError):
                    h3v.grid_distance(first, second)


if __name__ == '__main__':
    unittest.main()
