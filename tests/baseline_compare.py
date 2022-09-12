"""
A base class for adding file diffing to your integration tests.

This base class deals with:

* creating the name of a temporary file to write to,
* doing a udiff between the temp file and a baseline file
* cleaning up the temp file if all went well
* outputting the diff, and preserving the tmp file, if error
"""

import difflib
import os
import sys
import tempfile


class AutobuildBaselineCompare:
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

    def get_tmp_file(self):
        """
        Return a different tmp file for each test, so we can remove
        it if the test passes, or leave it around for debugging if it
        fails.
        """
        self.failed = False
        self.tmp_file = tempfile.NamedTemporaryFile(prefix="test_output_", delete=False).name
        return self.tmp_file

    def diff_tmp_file_against_baseline(self, baseline):
        """
        Do a udiff between the tmp file and a specified baseline file
        - raise an exception if different
        """
        output = self.tmp_file
        baseline = os.path.join(sys.path[0], baseline)
        with open(output, 'rb') as f:
            output_lines = [line.rstrip() for line in f]
        with open(baseline, 'rb') as f:
            baseline_lines = [line.rstrip() for line in f]
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

