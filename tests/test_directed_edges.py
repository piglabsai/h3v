"""Directed-edge topology, encoding, validation, and serialization contracts."""

import unittest

from h3.api import basic_int as h3

import h3v
from _h3v_core import _pack_radial


def voxel(cell, bin_number, resolution):
    return (_pack_radial(bin_number, resolution) << 64) | cell


class DirectedEdgeTests(unittest.TestCase):
    def check_edge(self, origin, destination):
        self.assertTrue(h3v.are_neighbor_voxels(origin, destination))
        edge = h3v.voxels_to_directed_edge(origin, destination)
        self.assertTrue(h3v.is_valid_directed_edge(edge))
        self.assertFalse(h3v.is_valid_voxel(edge))
        self.assertEqual(h3v.directed_edge_to_voxels(edge), (origin, destination))
        self.assertEqual(h3v.get_directed_edge_origin(edge), origin)
        self.assertEqual(h3v.get_directed_edge_destination(edge), destination)
        reverse = h3v.reverse_directed_edge(edge)
        self.assertEqual(h3v.directed_edge_to_voxels(reverse), (destination, origin))
        self.assertEqual(h3v.reverse_directed_edge(reverse), edge)
        self.assertIn(edge, h3v.origin_to_directed_edges(origin))
        self.assertEqual(h3v.str_to_int(h3v.int_to_str(edge)), edge)
        return edge

    def test_lateral_edges_and_pentagons(self):

        for resolution in (0, 1, 5, 15):
            for base in h3.get_res0_cells():
                cell = h3.cell_to_center_child(base, resolution)
                origin = voxel(cell, 15, 2)
                native_edges = h3.origin_to_directed_edges(cell)
                edges = h3v.origin_to_directed_edges(origin)
                self.assertEqual(len(edges), 7 if h3.is_pentagon(cell) else 8)
                self.assertEqual(len(set(edges)), len(edges))
                for native, edge in zip(native_edges, edges):
                    destination = voxel(h3.get_directed_edge_destination(native), 15, 2)
                    self.assertEqual(self.check_edge(origin, destination), edge)
                    self.assertEqual(edge & ((1 << 64) - 1), native)

    def test_radial_carries_zero_crossing_and_domain_limits(self):
        cell = h3.latlng_to_cell(52, 13, 9)
        for resolution in range(11):
            scale = 7**resolution
            total = 256 * scale
            for b in sorted({0, scale - 1, scale, 2 * scale - 1, total - 2}):
                origin, destination = voxel(cell, b, resolution), voxel(cell, b + 1, resolution)
                edge = self.check_edge(origin, destination)
                self.assertEqual(edge, origin | (2 << 116))
                self.assertEqual(h3v.reverse_directed_edge(edge), destination | (1 << 116))
            for b, missing_direction in ((0, 1), (total - 1, 2)):
                origin = voxel(cell, b, resolution)
                self.assertEqual(len(h3v.origin_to_directed_edges(origin)), 7)
                self.assert_invalid_edge(origin | (missing_direction << 116))

    def assert_invalid_edge(self, value):
        self.assertFalse(h3v.is_valid_directed_edge(value))
        for function in (h3v.get_directed_edge_origin, h3v.get_directed_edge_destination,
                         h3v.directed_edge_to_voxels, h3v.reverse_directed_edge):
            with self.assertRaises(ValueError):
                function(value)

    def test_invalid_types_and_corrupt_encodings(self):
        origin = h3v.latlngalt_to_voxel(52, 13, 0, 9, 7)
        lateral = h3v.origin_to_directed_edges(origin)[0]
        outward = origin | (2 << 116)
        for value in (None, True, 1.5, 'abc', -1, 0, 1 << 128, origin,
                      lateral & ((1 << 64) - 1), origin | (3 << 116),
                      lateral | (1 << 116), lateral | (1 << 127),
                      outward ^ (1 << 124), outward ^ 1,
                      outward | (15 << 112), outward | (15 << 100)):
            self.assert_invalid_edge(value)
        for bit in range(118, 124):
            for edge in (lateral, outward):
                bad = edge | (1 << bit)
                self.assert_invalid_edge(bad)
                with self.assertRaises(ValueError):
                    h3v.int_to_str(bad)
                with self.assertRaises(ValueError):
                    h3v.str_to_int(f'{bad:032x}')

        pentagon = h3.get_pentagons(0)[0]
        native = h3.origin_to_directed_edges(pentagon)[0]
        for direction in range(8):
            candidate = (native & ~(7 << 56)) | (direction << 56)
            packed = (_pack_radial(1, 0) << 64) | candidate
            self.assertEqual(h3v.is_valid_directed_edge(packed), h3.is_valid_directed_edge(candidate))

    def test_non_neighbors_and_invalid_voxels(self):
        cell = h3.latlng_to_cell(52, 13, 9)
        neighbor = h3.get_directed_edge_destination(h3.origin_to_directed_edges(cell)[0])
        origin = voxel(cell, 10, 2)
        for destination in (origin, voxel(cell, 12, 2), voxel(neighbor, 11, 2),
                            voxel(cell, 10, 3), voxel(h3.cell_to_parent(cell), 10, 2)):
            self.assertFalse(h3v.are_neighbor_voxels(origin, destination))
            with self.assertRaises(ValueError):
                h3v.voxels_to_directed_edge(origin, destination)
        for invalid in (True, None, 0, *h3v.origin_to_directed_edges(origin)):
            for first, second in ((origin, invalid), (invalid, origin)):
                with self.assertRaises(ValueError):
                    h3v.are_neighbor_voxels(first, second)
                with self.assertRaises(ValueError):
                    h3v.voxels_to_directed_edge(first, second)
            with self.assertRaises(ValueError):
                h3v.origin_to_directed_edges(invalid)

    def test_voxel_only_operations_reject_edges(self):
        origin = h3v.latlngalt_to_voxel(52, 13, 0, 9, 7)
        for edge in h3v.origin_to_directed_edges(origin):
            for function in (h3v.get_resolution, h3v.voxel_to_cell,
                             h3v.voxel_to_latlngalt, h3v.voxel_to_altitude_bounds,
                             h3v.voxel_to_boundary, h3v.voxel_volume):
                with self.assertRaises(ValueError):
                    function(edge)
            with self.assertRaises(ValueError):
                h3v.voxel_to_parent(edge, 8, 6)
            with self.assertRaises(ValueError):
                h3v.voxel_to_children(edge, refine_surface=True, refine_radial=True)


if __name__ == '__main__':
    unittest.main()
