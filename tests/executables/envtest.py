#!/usr/bin/env python3
import os
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
