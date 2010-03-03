#!/usr/bin/env python
#
# setup.py
#
# Copyright (C) 2009 Damien Churchill <damoxc@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.    If not, write to:
#   The Free Software Foundation, Inc.,
#   51 Franklin Street, Fifth Floor
#   Boston, MA    02110-1301, USA.
#

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '.pyrex'))

try:
    from setuptools import setup, Extension
except ImportError:
    import ez_setup
    ez_setup.use_setuptools()
    from setuptools import setup, Extension

from distutils import cmd, log
from distutils.command.clean import clean as _clean
from Cython.Distutils import build_ext as _build_ext

_extra_compile_args = [
    '-DMSDBLIB'
]

ROOT = os.path.dirname(__file__)
WINDOWS = False

if sys.platform == 'win32':
    WINDOWS = True
    freetds_dir = os.path.join(ROOT, 'win32', 'freetds')
    include_dirs = [os.path.join(freetds_dir, 'include')]
    library_dirs = [os.path.join(freetds_dir, 'lib')]
    libraries = [
        'msvcrt',
        'kernel32',
        'user32',
        'gdi32',
        'winspool',
        'ws2_32',
        'comdlg32',
        'advapi32',
        'shell32',
        'ole32',
        'oleaut32',
        'uuid',
        'odbc32',
        'odbccp32',
        'libTDS',
        'dblib'
    ]

else:
    include_dirs = [
        '/usr/local/include', '/usr/local/include/freetds',  # first local install
        '/usr/include', '/usr/include/freetds',   # some generic Linux paths
        '/usr/include/freetds_mssql',             # some versions of Mandriva 
        '/usr/local/freetds/include',             # FreeBSD
        '/usr/pkg/freetds/include'	              # NetBSD
    ]
    library_dirs = [
        '/usr/local/lib', '/usr/local/lib/freetds',
        '/usr/lib64',
        '/usr/lib', '/usr/lib/freetds',
        '/usr/lib/freetds_mssql', 
        '/usr/local/freetds/lib',
        '/usr/pkg/freetds/lib'
    ]
    libraries = [ "sybdb" ]   # on Mandriva you may have to change it to sybdb_mssql

if sys.platform == 'darwin':
    fink = '/sw/'
    include_dirs.insert(0, fink + 'include')
    library_dirs.insert(0, fink + 'lib')

    # some mac ports paths
    include_dirs += [
        '/opt/local/include',
        '/opt/local/include/freetds',
        '/opt/local/freetds/include'
    ]
    library_dirs += [
        '/opt/local/lib',
        '/opt/local/lib/freetds',
        '/opt/local/freetds/lib'
    ]

class build_ext(_build_ext):
    """
    Subclass the Cython build_ext command so it extracts freetds.zip if it
    hasn't already been done.
    """

    def run(self):
        # Not running on windows means we don't want to do this
        if not WINDOWS:
            return _build_ext.run(self)

        freetds_dir = os.path.join(ROOT, 'win32', 'freetds')

        # If the directory exists, it's probably been extracted already.
        if os.path.isdir(freetds_dir):
            return _build_ext.run(self)

        win32 = os.path.join(ROOT, 'win32')

        log.info('extracting FreeTDS')
        from zipfile import ZipFile
        zip = ZipFile(os.path.join(win32, 'freetds.zip'))
        zip.extractall(win32)
        zip.close()
        return _build_ext.run(self)

class clean(_clean):
    """
    Subclass clean so it removes all the Cython generated C files.
    """
    
    def run(self):
        _clean.run(self)
        for ext in self.distribution.ext_modules:
            cy_sources = [s for s in ext.sources if s.endswith('.pyx')]
            for cy_source in cy_sources:
                c_source = cy_source[:-3] + 'c'
                if os.path.exists(c_source):
                    log.info('removing %s', c_source)
                    os.remove(c_source)

setup(
    name  = 'pymssql',
    version = '1.9.906',
    description = 'A simple database interface to MS-SQL for Python.',
    long_description = 'A simple database interface to MS-SQL for Python.',
    author = 'Damien Churchill',
    author_email = 'damoxc@gmail.com',
    license = 'LGPL',
    url = 'http://pymssql.sourceforge.net',
    cmdclass = {'build_ext': build_ext, 'clean': clean},
    data_files = [
        ('', ['_mssql.pyx', 'pymssql.pyx'])
    ],
    ext_modules = [Extension('_mssql', ['_mssql.pyx'],
                             extra_compile_args = _extra_compile_args,
                             include_dirs = include_dirs,
                             library_dirs = library_dirs,
                             libraries = libraries),
                   Extension('pymssql', ['pymssql.pyx'],
                             extra_compile_args = _extra_compile_args,
                             include_dirs = include_dirs,
                             library_dirs = library_dirs,
                             libraries = libraries)]
)
