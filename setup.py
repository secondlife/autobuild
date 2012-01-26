#!/usr/bin/python
#
# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
# $/LicenseInfo$

from distribute_setup import use_setuptools
use_setuptools()
from setuptools import setup
import os.path

# most of this is shamelessly cloned from llbase's setup.py

# Version twiddling
# Each time we rebuild an autobuild package, manually increment the "build
# number" here, e.g. 0.8.1, 0.8.2, etc.
BUILD = 10                              # open-130, open-133
# But suppose we update our repository with new source and the version number
# embedded in the package itself changes, e.g. from 0.8 to 0.9 -- but we don't
# notice, simply incrementing the build number? The package build we expected
# to become 0.8.5 should really be 0.9.1 instead -- NOT 0.9.5.
VERSION_WHEN_LAST_PACKAGED = "0.8"

# from http://stackoverflow.com/questions/2058802/how-can-i-get-the-version-defined-in-setup-py-setuptools-in-my-package :
# "make a version.py in your package with a __version__ line, then read it
# from setup.py using execfile('mypackage/version.py'), so that it sets
# __version__ in the setup.py namespace."

# [We actually define AUTOBUILD_VERSION_STRING, but same general idea.]

# "DO NOT import your package from your setup.py... it will seem to work for
# you (because you already have your package's dependencies installed), but it
# will wreak havoc upon new users of your package, as they will not be able to
# install your package without manually installing the dependencies first."
# from autobuild.common import AUTOBUILD_VERSION_STRING
execfile(os.path.join("autobuild", "version.py"))
# The previous execfile better have defined AUTOBUILD_VERSION_STRING...
if AUTOBUILD_VERSION_STRING != VERSION_WHEN_LAST_PACKAGED:
    BUILD = 1


PACKAGE_NAME = 'autobuild'
LLAUTOBUILD_SOURCE = 'autobuild'
CLASSIFIERS = """\
Development Status :: 4 - Beta
Intended Audience :: Developers
License :: OSI Approved :: MIT License
Programming Language :: Python
Topic :: Software Development
Topic :: Software Development :: Libraries :: Python Modules
Operating System :: Microsoft :: Windows
Operating System :: Unix
"""

ext_modules = []

setup(
    name=PACKAGE_NAME,
    version="%s.%s" % (AUTOBUILD_VERSION_STRING, BUILD),
    author='Brad Linden',
    author_email='brad@lindenlab.com',
    url="http://wiki.secondlife.com/wiki/Autobuild",
    description='Linden Lab Automated Package Management and Build System',
    platforms=["any"],
    package_dir={PACKAGE_NAME:LLAUTOBUILD_SOURCE},
    packages=[PACKAGE_NAME],
    entry_points=dict(console_scripts=['autobuild=autobuild.autobuild_main:main']),
    scripts=[],
    license='MIT',
    classifiers=filter(None, CLASSIFIERS.split("\n")),
    #requires=['eventlet', 'elementtree'],
    #ext_modules=ext_modules,
    )
