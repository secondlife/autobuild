#!/usr/bin/python
"""\
@file   version.py
@author Nat Goodspeed
@date   2011-06-24
@brief  Define AUTOBUILD_VERSION_STRING

$LicenseInfo:firstyear=2011&license=internal$
Copyright (c) 2011, Linden Research, Inc.
$/LicenseInfo$
"""

# from http://stackoverflow.com/questions/2058802/how-can-i-get-the-version-defined-in-setup-py-setuptools-in-my-package :
# "make a version.py in your package with a __version__ line, then read it
# from setup.py using execfile('mypackage/version.py'), so that it sets
# __version__ in the setup.py namespace."

# [We actually define AUTOBUILD_VERSION_STRING, but same general idea.]

# "DO NOT import your package from your setup.py... it will seem to work for
# you (because you already have your package's dependencies installed), but it
# will wreak havoc upon new users of your package, as they will not be able to
# install your package without manually installing the dependencies first."

AUTOBUILD_VERSION_STRING = "0.8"
