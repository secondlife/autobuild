#!/usr/bin/python
# $LicenseInfo:firstyear=2021&license=mit$
# Copyright (c) 2021, Linden Research, Inc.
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
import os
import sys

from autobuild.executable import Executable

_SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))


def echo(text):
    return Executable(command=sys.executable, options=[os.path.join(_SCRIPT_DIR, "echo.py")], arguments=[text])


# Formally you might consider that noop.py and envtest.py are "arguments" rather
# than "options" -- but the way Executable is structured, if we pass
# them as "argument" then the "build" subcommand gets inserted before,
# which thoroughly confuses the Python interpreter.
noop = Executable(command=sys.executable, options=[os.path.join(_SCRIPT_DIR, "noop.py")])
envtest = Executable(command=sys.executable, options=[os.path.join(_SCRIPT_DIR, "envtest.py")])
