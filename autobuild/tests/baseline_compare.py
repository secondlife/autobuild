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

"""
A base class for adding file diffing to your integration tests.

This base class deals with:

* creating the name of a temporary file to write to, 
* doing a udiff between the temp file and a baseline file
* cleaning up the temp file if all went well
* outputting the diff, and preserving the tmp file, if error

Author : Martin Reddy
Date   : 2010-04-23
"""

from builtins import object
import os
import sys
import difflib

class AutobuildBaselineCompare(object):
    """
    Inherit from this base class to add file diff'ing functionality
    to your integrations tests. To use this class, simply call

    initialize_integration_test(<test_number>)

    from each of your unittest test_<test_number>() methods, and then
    from the tearDown() method call:

    cleanup_integration_test()

    Then you can generate output files using the self.tmp_file
    filename and call the diff_tmp_file_against_baseline() method to
    perform a udiff on two files. If the files are equivalent then
    the tmp file will get removed by the cleanup method. Otherwise,
    the test will fail and you will receive the udiff output. The
    tmp file will be preserved in the case of a failure.
    """

    failed = False
    tmp_file = None

    def get_tmp_file(self, n):
        """
        Return a different tmp file for each test, so we can remove
        it if the test passes, or leave it around for debugging if it
        fails.
        """
        self.failed = False
        self.tmp_file = os.path.join(sys.path[0], "test_output_%d.out" % n)
        return self.tmp_file

    def diff_tmp_file_against_baseline(self, baseline):
        """
        Do a udiff between the tmp file and a specified baseline file
        - raise an exception if different
        """
        output = self.tmp_file
        baseline = os.path.join(sys.path[0], baseline)
        output_lines = [x.rstrip() for x in file(output, 'rb').readlines()]
        baseline_lines = [x.rstrip() for x in file(baseline, 'rb').readlines()]
        udiff = difflib.unified_diff(baseline_lines, output_lines, fromfile=baseline,
                                     tofile=output, lineterm="")
        error = []
        for line in udiff:
            error.append(line)
        if error:
            self.failed = True
            self.fail("Output does not match baseline.\nBaseline: %s\nOutput: %s\nDiff:\n%s" %
                      (baseline, output, "\n".join(error)))

    def cleanup_tmp_file(self):
        """
        Remove our temp file, though only if the test succeeded
        """
        if not self.failed and self.tmp_file and os.path.exists(self.tmp_file):
            os.remove(self.tmp_file)

