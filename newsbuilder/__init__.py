# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
L{newsbuilder} public APIs
"""

from ._newsbuilder import (
    findTwistedProjects, replaceInFile,
    replaceProjectVersion, Project, generateVersionFileData,
    CommandFailed, runCommand, NewsBuilder, NotWorkingDirectory)

__all__ = [
    'findTwistedProjects',
    'replaceInFile',
    'replaceProjectVersion',
    'Project',
    'generateVersionFileData',
    'CommandFailed',
    'runCommand',
    'NewsBuilder',
    'NotWorkingDirectory',
    '__version__',
]

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
