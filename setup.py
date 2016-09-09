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

from setuptools import setup
import sys
import os.path

# most of this is shamelessly cloned from llbase's setup.py

# from http://stackoverflow.com/questions/2058802/how-can-i-get-the-version-defined-in-setup-py-setuptools-in-my-package :
# "make a version.py in your package with a __version__ line, then read it
# from setup.py using execfile('mypackage/version.py'), so that it sets
# __version__ in the setup.py namespace."

# [We actually define AUTOBUILD_VERSION_STRING, but same general idea.]

# "DO NOT import your package from your setup.py... it will seem to work for
# you (because you already have your package's dependencies installed), but it
# will wreak havoc upon new users of your package, as they will not be able to
# install your package without manually installing the dependencies first."
execfile(os.path.join("autobuild", "version.py"))
# The previous execfile better have defined AUTOBUILD_VERSION_STRING!
AUTOBUILD_VERSION_STRING                # NameError here means it didn't

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
    version=AUTOBUILD_VERSION_STRING,
    author='Oz Linden',
    author_email='oz@lindenlab.com',
    url="http://wiki.secondlife.com/wiki/Autobuild",
    description='Linden Lab Automated Package Management and Build System',
    platforms=["any"],
    package_dir={PACKAGE_NAME:LLAUTOBUILD_SOURCE},
    packages=[PACKAGE_NAME],
    entry_points=dict(console_scripts=['autobuild=autobuild.autobuild_main:main']),
    scripts=[],
    license='MIT',
    classifiers=filter(None, CLASSIFIERS.split("\n")),
    # argparse is specifically for Python 2.6 compatibility. If/when we drop
    # Python 2.6 support, the conditional argparse item can be removed from
    # install_requires: it's bundled with Python 2.7+.
    install_requires=['llbase', 'pydot'] + \
                     (['argparse'] if sys.version_info[:2] < (2, 7) else []),
    #ext_modules=ext_modules,
    )
