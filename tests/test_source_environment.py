import logging
import os
import shutil
import subprocess
import sys
import tempfile
from ast import literal_eval
from pprint import pformat

from autobuild import autobuild_tool_source_environment as atse
from tests.basetest import *
from tests.patch import patch


def assert_dict_subset(d, s):
    # Windows insists on capitalizing environment variables, so prepare a copy
    # of d with all-caps keys.
    dupper = dict((k.upper(), v) for k, v in d.items())
    missing = []
    mismatch = []
    for key, value in s.items():
        try:
            dval = dupper[key.upper()]
        except KeyError:
            missing.append(key)
        else:
            if dval != value:
                mismatch.append(key)

    if missing or mismatch:
        msg = [pformat(d), " does not contain ", pformat(s)]
        for label, keys in ("missing: ", missing), ("mismatch: ", mismatch):
            if keys:
                keys.sort()
                msg.extend((label, pformat(keys)))
        raise AssertionError('\n'.join(msg))

def assert_found_assignment(key, value, output):
    # shorthand for a regex search
    # Use triple quotes so we can readably embed both single and double
    # quotes, so we can succeed regardless of how the actual quoting is
    # expressed.
    # Set the MULTILINE flag so ^ and $ match internal line breaks.
    # Handle any level of indentation.
    return assert_found_in(r'''(?m)^ *%s=['"]%s["']$''' % (key, value), [output])

# for direct calls into do_source_environment(), simulate what's produced by
# argparse
class Args(object):
    def __init__(self, varsfile=None, config=None):
        self.varsfile = varsfile
        # -c argument is specified as action="append", which means
        # configurations attribute comes in as a possibly-empty list
        self.configurations = [config] if config is not None else []


@needs_nix
class TestSourceEnvironment(BaseTest):
    def setUp(self):
        BaseTest.setUp(self)
        # important to ensure certain variables are NOT set in the containing
        # environment during these tests
        self.restores = {}
        self.removes = []
        for var in [
            "AUTOBUILD_VARIABLES_FILE",
            ]:
            try:
                self.restores[var] = os.environ[var]
            except KeyError:
                self.removes.append(var)
            else:
                del os.environ[var]

        # create a temp directory
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

        for var, value in self.restores.items():
            os.environ[var] = value
        for var in self.removes:
            # an individual test might or might not set var
            os.environ.pop(var, None)
        BaseTest.tearDown(self)

    def autobuild_call(self, *args):
        """
        This method directly calls the autobuild source_environment
        implementation in the current (test) process, passing specified
        'args'. It's useful for (e.g.) checking thrown exceptions.
        """
        return atse.do_source_environment(Args(*args))

    def autobuild_outputs(self, *args):
        """
        This method runs autobuild source_environment as a child process (with
        passed 'args'), capturing and returning its stdout, stderr. It fails
        if the child process terminates with nonzero rc.
        """
        autobuild = subprocess.Popen((self.autobuild_bin, "source_environment") + args,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     universal_newlines=True)
        stdout, stderr = autobuild.communicate()
        rc = autobuild.wait()
        assert rc == 0, "%s source_environment terminated with %s:\n%s" % \
               (self.autobuild_bin, rc, stderr)
        return stdout.rstrip(), stderr.rstrip()

    if not sys.platform.startswith("win"):
        def source_env_and(self, args, commands):
            """
            This method runs a little bash script that runs autobuild
            source_environment (with args as specified in the sequence 'args'),
            evals its output and then performs whatever bash commands are passed
            in the string 'commands'.
            """
            # You may wonder why we explicitly pass 'bash -c' before the command
            # rather than shell=True. It's because on Windows, shell=True gets us
            # the .bat processor rather than bash. We specifically want bash on
            # all platforms.
            return subprocess.check_output(["bash", "-c", """\
    eval "$('%s' source_environment %s)"
    %s""" % (self.autobuild_bin,
             ' '.join("'%s'" % arg for arg in args),
             commands)], universal_newlines=True).rstrip()

        def shell_path(self, path):
            return path

    else: # Then There's Windows
        # On Windows, running
        # bash -c 'eval "$(autobuild source_environment)" ...'
        # is unreasonably difficult. We've set things up so that
        # self.autobuild_bin is the Windows .cmd file -- which won't work if
        # passed to bash. Okay, we tell bash to execute the OTHER script, the
        # one intended for bash. But that one depends on a shbang line
        # #!/usr/bin/env python
        # which (as desired) invokes the python.org Python interpreter...
        # passing it /cygdrive/c/path/to/our/autobuild... which fails
        # miserably. So on Windows, don't even try to run autobuild under
        # bash. Instead we're going to run autobuild source_environment using
        # self.autobuild(), capture its output, prepare a temp script file,
        # append the specified commands and run that script file with bash.
        def source_env_and(self, args, commands):
            srcenv = self.autobuild("source_environment", *args)
            scriptname = os.path.join(self.tempdir, "source_env_and.sh")
            with open(scriptname, "w", newline="\n") as scriptf:
                scriptf.write(srcenv)
                scriptf.write('\n')
                scriptf.write(commands)
            try:
                return subprocess.check_output([self.cygwin_bash(), "-c",
                                                self.shell_path(scriptname)], universal_newlines=True).rstrip()
            finally:
                os.remove(scriptname)

        @staticmethod
        def cygwin_bash():
            """Get path to cygwin/mingw bash. This is necessary because some windows environments might also have WSL installed."""
            return subprocess.check_output(["cygpath", "-w", "/usr/bin/bash"], universal_newlines=True).rstrip()

        @staticmethod
        def shell_path(path):
            return subprocess.check_output(["cygpath", "-u", path], universal_newlines=True).rstrip()

    def read_variables(self, *args):
        """
        This method uses source_env_and() to get bash to eval
        source_environment output (with passed 'args'), uses python to
        serialize the whole resulting environment to stdout, parses stdout
        back into a dict, eliminates any entries identical to our os.environ
        (since they're merely inherited) and returns the remaining dict.
        """
        # Once we've run source_environment, if we want results to be visible
        # to the Python pprint(os.environ), we must explicitly export them.
        # This means we can't use this function to distinguish between
        # exported and unexported variables -- but we'd much rather be able to
        # detect whether they're set.
        vars = literal_eval(self.source_env_and(args, """\
for var in $(set | grep '^[^ ]' | cut -s -d= -f 1)
do export $var
done
'%s' -c 'import os, pprint
pprint.pprint(dict(os.environ))'""" % self.shell_path(sys.executable)))
        # filter out anything inherited from our own environment
        for var, value in os.environ.items():
            if value == vars.get(var):
                del vars[var]
        return vars

    def test_env(self):
        assert 'environment_template' in dir(atse)

    def test_remove_switch(self):
        self.assertEqual(self.source_env_and([], """\
switches='abc def ghi'
remove_switch def $switches"""), "abc ghi")

    def test_replace_switch(self):
        # replace_switch makes no guarantees about the order in which the
        # switches are returned.
        self.assertEqual(set(self.source_env_and([], """\
switches='abc def ghi'
replace_switch def xyz $switches""").split()),
                      set(["abc", "xyz", "ghi"]))

    def test_no_arg_warning(self):
        # autobuild source_environment with no arg
        stdout, stderr = self.autobuild_outputs()
        # ensure that autobuild produced a warning
        assert_in("no build variables", stderr)
        # but emitted normal output anyway
        assert_in("set_build_variables", stdout)

    def find_data(self, filename):
        return os.path.join(os.path.dirname(__file__), "data", filename)

    def test_arg_no_warning(self):
        # autobuild source_environment path/to/empty
        stdout, stderr = self.autobuild_outputs(self.find_data("empty"))
        # This also verifies that source_environment doesn't produce errors
        # when handed an empty script file.
        self.assertEqual(stderr, "")

    def test_var_no_warning(self):
        os.environ["AUTOBUILD_VARIABLES_FILE"] = self.find_data("empty")
        # autobuild source_environment with no arg but AUTOBUILD_VARIABLES_FILE
        stdout, stderr = self.autobuild_outputs()
        self.assertEqual(stderr, "")

    def test_no_MAKEFLAGS(self):
        assert_not_in("MAKEFLAGS", self.autobuild_outputs()[0])

    def test_no_file_error(self):
        with exc(atse.SourceEnvError, "can't read.*nonexistent"):
            # autobuild source_environment nonexistent_pathname
            self.autobuild_call(self.find_data("nonexistent"))

    def test_only_comments(self):
        # this would blow up if it doesn't handle comments or blank lines
        self.autobuild_outputs(self.find_data("only_comments"))

    def test_bad_assignment(self):
        # verify that we report the filename and line number
        # escape the parens to match them literally
        with exc(atse.SourceEnvError, r"bad_assignment\(5\).*assignment"):
            # autobuild source_environment bad_assignment
            self.autobuild_call(self.find_data("bad_assignment"))

    def test_bad_substitution(self):
        with exc(atse.SourceEnvError, r"bad_substitution\(3\).*substitution"):
            self.autobuild_call(self.find_data("bad_substitution"))

    def test_bad_variable(self):
        with exc(atse.SourceEnvError, r"bad_variable\(2\).*undefined.*def"):
            self.autobuild_call(self.find_data("bad_variable"))

    def test_good_variable(self):
        vars = self.read_variables(self.find_data("good_variable"))
        # Don't try for exact dict equality because source_environment is
        # going to stick additional items into the dict.
        assert_dict_subset(vars, {"abc": "xyz", "def": "xyz"})

    def test_platform_shorthand(self):
        # Seems like we shouldn't be able to overwrite sys.platform! But since
        # we can, that seems preferable to deriving the variable name for the
        # current platform in parallel with the autobuild implementation.
        # Initially I patched sys.platform to "win32", figuring that Windows
        # is our most important platform. The trouble with that is that on any
        # other platform, autobuild source_environment naturally complains
        # that Visual Studio isn't installed! So go for "darwin" instead.
        with patch(sys, "platform", "darwin"), capture_stdout_buffer() as outbuf:
            # Patching sys.platform of course only affects THIS process.
            # Therefore we must use autobuild_call() rather than any of the
            # methods that run autobuild source_environment as a child
            # process.
            self.autobuild_call(self.find_data("darwin"))
        stdout = outbuf.getvalue().decode("utf-8")
        assert_found_assignment("LL_BUILD_DARWIN_RELEASE", "darwin release", stdout)
        assert_found_assignment("LL_BUILD_RELEASE", "darwin release", stdout)
        assert_found_assignment("SOMETHING_ELSE", "something else", stdout)
        assert_not_found_in(r'^ *LL_BUILD=', stdout)

    def test_bad_platform_warning(self):
        # For autobuild_call(), capturing warning output isn't as
        # straightforward as CaptureStdout or CaptureStderr because the logger
        # output isn't necessarily flushed to stderr yet. So to capture
        # warnings emitted by an autobuild_call() call, temporarily attach an
        # extra handler to the logger used by autobuild source_environment.
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        atse.logger.addHandler(handler)
        try:
            with patch(sys, "platform", "strange"), capture_stdout_buffer():
                self.autobuild_call(self.find_data("darwin"))
        finally:
            atse.logger.removeHandler(handler)
        stderr = stream.getvalue()
        assert_in("platform", stderr)
        assert_in("strange", stderr)

    def test_config_shorthand(self):
        with patch(sys, "platform", "darwin"), capture_stdout_buffer() as outbuf:
            self.autobuild_call(self.find_data("darwin"), "RelWithDebInfo")
        stdout = outbuf.getvalue().decode("utf-8")
        assert_found_assignment("LL_BUILD_DARWIN_RELEASE", "darwin release", stdout)
        assert_found_assignment("LL_BUILD_RELEASE", "darwin release", stdout)
        assert_found_assignment("SOMETHING_ELSE", "something else", stdout)
        assert_not_found_in(r'^ *LL_BUILD=', stdout)

        with patch(sys, "platform", "darwin"), capture_stdout_buffer() as outbuf:
            self.autobuild_call(self.find_data("darwin"), "Release")
        stdout = outbuf.getvalue().decode("utf-8")
        assert_found_assignment("LL_BUILD_DARWIN_RELEASE", "darwin release", stdout)
        assert_found_assignment("LL_BUILD_RELEASE", "darwin release", stdout)
        assert_found_assignment("LL_BUILD", "darwin release", stdout)
        assert_found_assignment("SOMETHING_ELSE", "something else", stdout)

    @needs_cygwin
    def test_vstoolset_set(self):
        # n.b. This test will need to be updated from time to time:
        # AUTOBUILD_VSVER is validated against the Visual Studio versions
        # installed on the host system.
        with envvar("AUTOBUILD_VSVER", "170"):
            vars = self.read_variables(self.find_data("empty"))
        self.assertEqual(vars["AUTOBUILD_WIN_VSTOOLSET"], "v143")
