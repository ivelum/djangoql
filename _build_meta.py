"""In-tree PEP 517 build backend.

Wraps setuptools' build backend so the gettext ``.mo`` catalogs are compiled
from their ``.po`` sources (via :func:`_translations.compile_catalogs`, using
Babel -- no system gettext needed) immediately before each build step. The
``.mo`` files are not tracked in git; they are generated here for both the
wheel and the sdist.

Configured in ``pyproject.toml`` as::

    [build-system]
    requires = ["setuptools>=77.0", "babel"]
    build-backend = "_build_meta"
    backend-path = ["."]
"""

# Re-export every hook setuptools defines so this module is a drop-in
# build-backend; the wrappers below override the ones that emit artifacts.
from setuptools import build_meta as _setuptools_backend
from setuptools.build_meta import *  # noqa: F401,F403

from _translations import compile_catalogs


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    compile_catalogs()
    return _setuptools_backend.build_wheel(
        wheel_directory, config_settings, metadata_directory
    )


def build_sdist(sdist_directory, config_settings=None):
    compile_catalogs()
    return _setuptools_backend.build_sdist(sdist_directory, config_settings)


def build_editable(
    wheel_directory, config_settings=None, metadata_directory=None
):
    compile_catalogs()
    return _setuptools_backend.build_editable(
        wheel_directory, config_settings, metadata_directory
    )
