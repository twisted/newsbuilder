# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
L{newsbuilder} public APIs
"""

from ._newsbuilder import (
    CommandFailed, runCommand, NewsBuilder, NewsBuilderOptions,
    NewsBuilderScript)

__all__ = [
    'CommandFailed',
    'runCommand',
    'NewsBuilder',
    'NewsBuilderOptions',
    'NewsBuilderScript',
    '__version__',
]

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
