#!/usr/bin/python
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

import os
import re
import subprocess
import sys

# This script is intended to test whether autobuild sets the AUTOBUILD
# environment variable for its child processes. Its name, envtest.py, is
# specifically chosen to cause tests to fail to recognize it as a test
# module. Instead, it is executed by test_build.TestEnvironment.test_env(), by
# specifying it as the build command in the configuration.

if __name__ == '__main__':
    # Verify that we can execute whatever the AUTOBUILD env var points to.
    # This is not the same as os.access($AUTOBUILD, os.X_OK): $AUTOBUILD
    # should be a command we can execute, but (at least on Windows) the
    # corresponding executable file may be $AUTOBUILD.cmd or $AUTOBUILD.exe or
    # some such.
    command = [os.environ["AUTOBUILD"], "--version"]
    autobuild = subprocess.Popen(command,
                                 stdout=subprocess.PIPE,
                                 # Use command shell to perform that search.
                                 shell=sys.platform.startswith("win"),
                                 universal_newlines=True)
    stdout, stderr = autobuild.communicate()
    rc = autobuild.wait()
    try:
        assert rc == 0, "%s => %s" % (' '.join(command), rc)
        assert stdout.startswith("autobuild "), \
               "does not look like autobuild --version output:\n" + stdout
    except AssertionError as err:
        print("***Failed command: %s" % command, file=sys.stderr)
        raise
