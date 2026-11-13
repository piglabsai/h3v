"""Category exports, dependencies, documentation, and direct imports."""
import importlib
from pathlib import Path
import re
import subprocess
import sys
import unittest

import h3v


CATEGORIES = (
    ('Indexing', 'h3v_indexing', ['latlngalt_to_voxel', 'voxel_to_latlngalt', 'ecef_to_voxel', 'voxel_to_ecef',
                               'voxel_to_altitude_bounds', 'voxel_to_boundary']),
    ('Inspection', 'h3v_inspection', ['get_resolution', 'is_valid_voxel', 'voxel_to_cell',
                                   'int_to_str', 'str_to_int']),
    ('Traversal', 'h3v_traversal', ['grid_distance', 'grid_ring', 'grid_disk']),
    ('Hierarchy', 'h3v_hierarchy', ['voxel_to_parent', 'voxel_to_children']),
    ('Regions', 'h3v_regions', []),
    ('Directed edges', 'h3v_directed_edges', ['are_neighbor_voxels', 'voxels_to_directed_edge', 'is_valid_directed_edge', 'get_directed_edge_origin', 'get_directed_edge_destination', 'directed_edge_to_voxels', 'origin_to_directed_edges', 'reverse_directed_edge']),
    ('Vertexes', 'h3v_vertexes', []),
    ('Geometry', 'h3v_geometry', ['voxel_volume', 'voxels_to_line', 'voxels_to_vector_ecef', 'voxels_to_great_circle', 'visibility_cap_radius']),
    ('Miscellaneous', 'h3v_miscellaneous', ['authalic_earth_radius',
                                         'RADIAL_BASE_STEP', 'MAX_RADIAL_RESOLUTION', 'MAX_ALTITUDE']),
)


class ModuleLayoutTests(unittest.TestCase):
    def test_public_facade_reexports_categories_in_reference_order(self):
        expected = []
        for title, module_name, names in CATEGORIES:
            module = importlib.import_module(module_name)
            self.assertEqual(module.__all__, names)
            expected.extend(names)
            for name in names:
                value = getattr(module, name)
                self.assertIs(getattr(h3v, name), value)
                if callable(value):
                    self.assertEqual(value.__module__, module_name)
            if not names:
                self.assertTrue(module.__doc__)
                self.assertFalse(any(callable(value) for name, value in vars(module).items()
                                     if not name.startswith('__')))
        self.assertEqual(h3v.__all__, expected)
        self.assertEqual(len(expected), len(set(expected)))

    def test_shared_core_is_independent_and_category_imports_work(self):
        module_names = [name for _, name, _ in CATEGORIES]
        for first in ['_h3v_core', *module_names, 'h3v']:
            code = f'import {first}\n'
            if first == '_h3v_core':
                code += ("import sys\nassert 'h3v' not in sys.modules\n"
                         "assert not any(name.startswith('h3v_') for name in sys.modules)\n")
            code += '''import h3v, h3v_indexing, h3v_geometry
voxel = h3v_indexing.latlngalt_to_voxel(52, 13, 0, 9, 10)
assert h3v.get_resolution(voxel) == (9, 10)
assert h3v_geometry.voxel_volume(voxel) > 0
assert h3v_geometry.voxels_to_line(voxel, voxel)[0] == 0
assert h3v.voxels_to_line is h3v_geometry.voxels_to_line
'''
            result = subprocess.run([sys.executable, '-I', '-B', '-c', code],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_api_references_match_category_and_function_order(self):
        docs = Path(__file__).resolve().parents[1] / 'docs'
        for filename in ('api_quick.md', 'api_reference.md'):
            text = (docs / filename).read_text()
            self.assertEqual(re.findall(r'^## (.+)$', text, re.M),
                             [title for title, _, _ in CATEGORIES])
            if filename == 'api_quick.md':
                functions = re.findall(r'^   ([a-z][a-z_]+)$', text, re.M)
            else:
                functions = re.findall(r'^\.\. autofunction:: h3v\.([a-z_]+)$', text, re.M)
            self.assertEqual(functions, [name for _, _, names in CATEGORIES for name in names
                                         if callable(getattr(h3v, name))])


if __name__ == '__main__':
    unittest.main()
