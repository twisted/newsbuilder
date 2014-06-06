# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Distutils installer for Newsbuilder
"""

from setuptools import setup

def read(path):
    """
    Read the contents of a file.
    """
    with open(path) as f:
        return f.read()



if __name__ == '__main__':
    setup(
        classifiers=[
            'Intended Audience :: Developers',
            'Development Status :: 2 - Pre-Alpha',
            'License :: OSI Approved :: MIT License',
            'Operating System :: OS Independent',
            'Programming Language :: Python',
            'Programming Language :: Python :: 2',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: Implementation :: CPython',
            'Programming Language :: Python :: Implementation :: PyPy',
        ],
        name='newsbuilder',
        version='0.1',
        description=(
            'Automatically generate and manage a NEWS file from snippets '
            'stored in per-ticket text files.'),
        install_requires=['twisted'],
        keywords='release',
        license='MIT',
        packages=['newsbuilder', 'newsbuilder.test'],
        url='https://github.com/twisted/newsbuilder',
        maintainer='Twisted Matrix Laboratories',
        maintainer_email='twisted-python@twistedmatrix.com',
        long_description=read('README.rst'),
        scripts=[
            'bin/newsbuilder'
        ],
    )
