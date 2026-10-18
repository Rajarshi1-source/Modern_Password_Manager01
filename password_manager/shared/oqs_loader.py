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

def _wrapper_candidates():
    """
    The paths liboqs-python 0.16.0.1 tries, in its order (``_load_liboqs`` /
    ``_load_shared_obj``): ``find_library("liboqs")``, ``find_library("oqs")``,
    then the ONE install dir (``$OQS_INSTALL_PATH`` if set, else
    ``$HOME/_oqs``): ``bin/oqs.dll``/``bin/liboqs.dll`` on Windows,
    ``lib{,64}/liboqs.dylib`` on macOS, ``lib{,64}/liboqs.so`` (unversioned)
    elsewhere. Anything outside this list is invisible to the wrapper, which
    would then run its installer, so it must not count as "installed" here.
    """
    candidates = []
    for name in ('oqs', 'liboqs'):  # the wrapper inserts each at index 0
        try:
            found = ctypes.util.find_library(name)
        except Exception:  # find_library shells out (ldconfig/gcc) on Linux
            found = None
        if found:
            candidates.insert(0, found)
    root = os.environ.get('OQS_INSTALL_PATH')
    root = Path(root) if root is not None else Path.home() / '_oqs'
    system = platform.system()
    if system == 'Windows':
        candidates += [str(root / 'bin' / f) for f in ('oqs.dll', 'liboqs.dll')]
    else:
        filename = 'liboqs.dylib' if system == 'Darwin' else 'liboqs.so'
        candidates += [str(root / sub / filename) for sub in ('lib', 'lib64')]
    return candidates


def _loadable(path) -> bool:
    """Whether the wrapper's loader would succeed on ``path``."""
    loader = ctypes.windll if platform.system() == 'Windows' else ctypes.cdll
    try:
        loader.LoadLibrary(path)
    except OSError:
        return False
    return True


def find_liboqs():
    """
    The first liboqs the wrapper would load, or None.

    Checked by actually loading it: a stale or broken file on a searched
    path would otherwise pass, and the wrapper, failing to load it, would
    fall back to its download-and-build installer.
    """
    for candidate in _wrapper_candidates():
        if _loadable(candidate):
            return candidate
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
