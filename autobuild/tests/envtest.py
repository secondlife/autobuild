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
import sys
import re
import subprocess

if __name__ == '__main__':
    # Verify that we can execute whatever the AUTOBUILD env var points to.
    # This is not the same as os.access($AUTOBUILD, os.X_OK): $AUTOBUILD
    # should be a command we can execute, but (at least on Windows) the
    # corresponding executable file may be $AUTOBUILD.cmd or $AUTOBUILD.exe or
    # some such.
    AUTOBUILD = os.environ["AUTOBUILD"]
    # HACK HACK HACK: Specifically when running self-tests on TeamCity under
    # build.sh under cygwin bash, AUTOBUILD is set to (e.g.)
    # "/cygdrive/c/some/path/autobuild.cmd". OPEN-259 mandates that we leave
    # any existing AUTOBUILD variable alone, so that's how it arrives here
    # too. Naturally, subprocess.Popen() knows nothing of /cygdrive/c. Fix
    # that. We believe this particular badness affects only this test,
    # otherwise we'd make the change in central autobuild execution machinery
    # instead of here in an individual test script.
    match = re.match(r"/cygdrive/(.)/", AUTOBUILD)
    if match:
        # match.group(1) is the drive letter;
        # [match.end(0):] strips off the entire matched prefix.
        AUTOBUILD = "%s:/%s" % (match.group(1), AUTOBUILD[match.end(0):])
    command = [AUTOBUILD, "--version"]
    autobuild = subprocess.Popen(command,
                                 stdout=subprocess.PIPE,
                                 # Use command shell to perform that search.
                                 shell=sys.platform.startswith("win"))
    stdout, stderr = autobuild.communicate()
    rc = autobuild.wait()
    assert rc == 0, "%s => %s" % (' '.join(command), rc)
    assert stdout.startswith("autobuild "), \
           "does not look like autobuild --version output:\n" + stdout
