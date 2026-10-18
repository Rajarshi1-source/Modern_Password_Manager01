"""
shared.oqs_loader: liboqs-python must never be imported when the liboqs C
library is missing, because its import would then download and build liboqs
(git clone + CMake) inside the running process.
"""
import importlib.abc
import sys
import types
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

    def test_find_liboqs_checks_the_install_path(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            lib = Path(tmp, 'lib')
            lib.mkdir()
            name = {'Windows': 'oqs.dll', 'Darwin': 'liboqs.9.dylib'}.get(
                oqs_loader.platform.system(), 'liboqs.so.9')
            (lib / name).write_bytes(b'')
            with patch.object(oqs_loader.ctypes.util, 'find_library', return_value=None), \
                    patch.dict('os.environ', {'OQS_INSTALL_PATH': tmp}):
                self.assertEqual(oqs_loader.find_liboqs(), str(lib / name))
            with patch.object(oqs_loader.ctypes.util, 'find_library', return_value=None), \
                    patch.dict('os.environ', {'OQS_INSTALL_PATH': str(Path(tmp, 'nothing'))}), \
                    patch.object(oqs_loader.Path, 'home', return_value=Path(tmp, 'nohome')):
                self.assertIsNone(oqs_loader.find_liboqs())
