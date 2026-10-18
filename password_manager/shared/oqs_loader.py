"""
Import liboqs-python only when the liboqs C library is already installed.

liboqs-python (0.10 through 0.16.0.1) reacts to a missing shared library by
installing one at import time: it runs ``git clone`` and a CMake build of
liboqs into ``$HOME/_oqs`` and loads the result. For this backend that would
mean fetching and compiling cryptographic code from the network inside a
web or Celery process, outside the pinned, SHA-asserted build in
docker/backend/Dockerfile (0.16.0.1 itself fixes a command injection in that
installer). So every backend module imports the wrapper through
``import_oqs()``, which refuses unless the library can already be found, and
the caller's existing "liboqs unavailable" handling (fail closed unless
QUANTUM_CRYPTO['ALLOW_SIMULATION']) takes over.
"""

import ctypes.util
import os
import platform
from pathlib import Path

_LIB_NAMES = ('oqs', 'liboqs')


def _install_dirs():
    root = os.environ.get('OQS_INSTALL_PATH')
    roots = [Path(root)] if root else []
    roots.append(Path.home() / '_oqs')  # where the wrapper's auto-installer puts it
    for r in roots:
        for sub in ('lib', 'lib64', 'bin'):
            yield r / sub


def find_liboqs():
    """Path or soname of an installed liboqs shared library, or None."""
    for name in _LIB_NAMES:
        try:
            found = ctypes.util.find_library(name)
        except Exception:  # find_library shells out (ldconfig/gcc) on Linux
            found = None
        if found:
            return found
    if platform.system() == 'Windows':
        patterns = ('oqs.dll', 'liboqs.dll')
    elif platform.system() == 'Darwin':
        patterns = ('liboqs*.dylib',)
    else:
        patterns = ('liboqs.so*',)
    for directory in _install_dirs():
        for pattern in patterns:
            match = next(iter(sorted(directory.glob(pattern))), None)
            if match is not None:
                return str(match)
    return None


def import_oqs():
    """
    Return the ``oqs`` module, or raise ImportError if liboqs is not
    installed (instead of letting the wrapper download and build it).
    """
    if find_liboqs() is None:
        raise ImportError(
            'liboqs shared library not found; not importing liboqs-python, '
            'whose import would otherwise download and build liboqs at runtime'
        )
    import oqs
    return oqs
