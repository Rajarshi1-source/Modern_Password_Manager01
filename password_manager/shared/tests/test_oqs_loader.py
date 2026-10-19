"""
shared.oqs_loader: liboqs-python must never be imported when the liboqs C
library is missing, because its import would then download and build liboqs
(git clone + CMake) inside the running process.
"""
import importlib.abc
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from shared import oqs_loader


class _RecordOqsImports(importlib.abc.MetaPathFinder):
    def __init__(self):
        self.attempts = 0

    def find_spec(self, name, path=None, target=None):
        if name == 'oqs':
            self.attempts += 1
        return None


def _no_find_library():
    return patch.object(oqs_loader.ctypes.util, 'find_library', return_value=None)


def _install_path(path):
    return patch.dict('os.environ', {'OQS_INSTALL_PATH': str(path)})


class OqsLoaderTests(SimpleTestCase):
    def test_missing_library_refuses_without_importing_the_wrapper(self):
        finder = _RecordOqsImports()
        saved = sys.modules.pop('oqs', None)
        sys.meta_path.insert(0, finder)
        try:
            with patch.object(oqs_loader, 'find_liboqs', return_value=None):
                with self.assertRaisesRegex(ImportError, 'liboqs shared library not found'):
                    oqs_loader.import_oqs()
        finally:
            sys.meta_path.remove(finder)
            if saved is not None:
                sys.modules['oqs'] = saved
        self.assertEqual(finder.attempts, 0)

    def test_installed_library_imports_the_wrapper(self):
        fake = types.ModuleType('oqs')
        with patch.dict(sys.modules, {'oqs': fake}), \
                patch.object(oqs_loader, 'find_liboqs', return_value='liboqs.so.9'):
            self.assertIs(oqs_loader.import_oqs(), fake)

    def _system_file(self):
        return {'Windows': ('bin', 'oqs.dll'), 'Darwin': ('lib', 'liboqs.dylib')}.get(
            oqs_loader.platform.system(), ('lib', 'liboqs.so'))

    def test_only_the_wrappers_install_dir_is_searched(self):
        # With OQS_INSTALL_PATH set, liboqs-python does NOT look in $HOME/_oqs,
        # so neither may the loader.
        with _no_find_library(), _install_path('/opt/custom-oqs'), \
                patch.object(oqs_loader.Path, 'home', return_value=Path('/home/app')):
            candidates = oqs_loader._wrapper_candidates()
        self.assertTrue(candidates)
        root = Path('/opt/custom-oqs').parts[:3]
        self.assertTrue(all(Path(c).parts[:3] == root for c in candidates))
        self.assertFalse(any('_oqs' in c for c in candidates))

    def test_versioned_soname_is_not_a_wrapper_path(self):
        if oqs_loader.platform.system() in ('Windows', 'Darwin'):
            self.skipTest('Linux naming')
        with _no_find_library(), _install_path('/x'):
            self.assertNotIn('/x/lib/liboqs.so.9', oqs_loader._wrapper_candidates())

    def test_find_library_results_come_first_in_the_wrappers_order(self):
        results = {'oqs': 'oqs-result', 'liboqs': 'liboqs-result'}
        with patch.object(oqs_loader.ctypes.util, 'find_library', side_effect=results.get):
            candidates = oqs_loader._wrapper_candidates()
        self.assertEqual(candidates[:2], ['liboqs-result', 'oqs-result'])

    def test_a_present_but_unloadable_library_does_not_count(self):
        sub, name = self._system_file()
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, sub).mkdir()
            Path(tmp, sub, name).write_bytes(b'not a shared library')
            with _no_find_library(), _install_path(tmp):
                self.assertIsNone(oqs_loader.find_liboqs())
                with self.assertRaises(ImportError):
                    oqs_loader.import_oqs()

    def test_the_first_loadable_candidate_is_returned(self):
        with patch.object(oqs_loader, '_wrapper_candidates', return_value=['a', 'b', 'c']), \
                patch.object(oqs_loader, '_loadable', side_effect=lambda p: p in ('b', 'c')):
            self.assertEqual(oqs_loader.find_liboqs(), 'b')
