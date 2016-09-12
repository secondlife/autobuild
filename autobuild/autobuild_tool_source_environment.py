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
from ast import literal_eval
import itertools
import logging
from pprint import pformat
import re
import shutil
import stat
import subprocess
import tempfile

import common
import autobuild_base


logger = logging.getLogger('autobuild.source_environment')

# for the time being, we expect that we're checked out side-by-side with
# parabuild buildscripts, so back up a level to find $helper.
get_params = None
helper = os.path.join(os.path.dirname(__file__),
                      os.pardir,
                      os.pardir,
                      'buildscripts/hg/bin')
if os.path.exists(helper):
    # Append helper to sys.path.
    _helper_idx = len(sys.path)
    sys.path.append(helper)
    assert sys.path[_helper_idx] == helper

    try:
        import get_params
        logger.info("found get_params: '%s'" % get_params.__file__)
    except ImportError:
        # restore original sys.path value
        assert sys.path[_helper_idx] == helper
        del sys.path[_helper_idx]

class SourceEnvError(common.AutobuildError):
    pass

def load_vsvars(vsver):
    """
    Return a dict of environment variables set by the applicable Visual Studio
    vcvars*.bat file. Note: any variable identical to the corresponding
    current os.environ entry is assumed to be inherited rather than set. The
    returned dict contains only variables added or changed by vcvars*.bat.

    The relevant Visual Studio version is specified by the vsver parameter,
    according to Microsoft convention:

    '100' selects Visual Studio 2010
    '120' selects Visual Studio 2013 (version 12.0)
    etc.

    os.environ['AUTOBUILD_ADDRSIZE'] (set by common.establish_platform()) also
    participates in the selection of the .bat file. When it's '32', the .bat
    file will set variables appropriate for a 32-bit build, and similarly when
    it's '64'.
    """
    key = "VS%sCOMNTOOLS" % vsver
    logger.debug("vsver %s, key %s" % (vsver, key))
    try:
        # We've seen traceback output from this if vsver doesn't match an
        # environment variable. Produce a reasonable error message instead.
        VSxxxCOMNTOOLS = os.environ[key]
    except KeyError:
        candidates = [k for k in os.environ.iterkeys()
                      if re.match(r"VS.*COMNTOOLS$", k)]
        explain = " (candidates: %s)" % ", ".join(candidates) if candidates \
                  else ""
        raise SourceEnvError("No env variable %s, is Visual Studio %s installed?%s" %
                             (key, vsver, explain))

    # VSxxxCOMNTOOLS will be something like:
    # C:\Program Files (x86)\Microsoft Visual Studio 12.0\Common7\Tools\
    # We want to find vcvarsall.bat, which will be somewhere like
    # C:\Program Files (x86)\Microsoft Visual Studio 12.0\VC\vcvarsall.bat
    # Assuming that we can just find %VSxxxCOMNTOOLS%..\..\VC seems a little
    # fragile across installs or (importantly) across future VS versions.
    # Instead, use %VSxxxCOMNTOOLS%VCVarsQueryRegistry.bat to populate
    # VCINSTALLDIR.
    VCVarsQueryRegistry_base = "VCVarsQueryRegistry.bat"
    VCVarsQueryRegistry = os.path.join(VSxxxCOMNTOOLS, VCVarsQueryRegistry_base)
    # Failure to find any of these .bat files could produce really obscure
    # execution errors. Make the error messages as explicit as we can.
    if not os.path.exists(VCVarsQueryRegistry):
        raise SourceEnvError("%s not found at %s: %s" %
                             (VCVarsQueryRegistry_base, key, VSxxxCOMNTOOLS))

    # Found VCVarsQueryRegistry.bat, run it.
    vcvars = get_vars_from_bat(VCVarsQueryRegistry)

    # Then we can find %VCINSTALLDIR%vcvarsall.bat.
    try:
        VCINSTALLDIR = vcvars["VCINSTALLDIR"]
    except KeyError:
        raise SourceEnvError("%s did not populate VCINSTALLDIR" % VCVarsQueryRegistry)

    vcvarsall_base = "vcvarsall.bat"
    vcvarsall = os.path.join(VCINSTALLDIR, vcvarsall_base)
    if not os.path.exists(vcvarsall):
        raise SourceEnvError("%s not found at VCINSTALLDIR: %s" %
                             (vcvarsall_base, VCINSTALLDIR))

    # vcvarsall.bat accepts a single argument: the target architecture, e.g.
    # "x86" or "x64".
    # Let KeyError, if any, propagate: lack of AUTOBUILD_ADDRSIZE would be an
    # autobuild coding error. So would any value for that variable other than
    # what's stated below.
    arch = {
        '32': 'x86',
        '64': 'x64',
        }[os.environ["AUTOBUILD_ADDRSIZE"]]
    vcvars = get_vars_from_bat(vcvarsall, arch)

    # Now weed out of vcvars anything identical to OUR environment. Retain
    # only environment variables actually modified by vcvarsall.bat.
    # Use items() rather than iteritems(): capture the list of items up front
    # instead of trying to traverse vcvars while modifying it.
    for var, value in vcvars.items():
        # Bear in mind that some variables were introduced by vcvarsall.bat and
        # are therefore NOT in our os.environ.
        if os.environ.get(var) == value:
            # Any environment variable from our batch script that's identical
            # to our own os.environ was simply inherited. Discard it.
            del vcvars[var]
    logger.debug("set by %s %s:\n%s" % (vcvarsall, arch, pformat(vcvars)))

    return vcvars

def get_vars_from_bat(batpath, *args):
    # Invent a temp filename into which to capture our script output. Some
    # versions of vsvars32.bat emit stdout, some don't; we've been bitten both
    # ways. Bypass that by not commingling our desired output into stdout.
    temp_output = tempfile.NamedTemporaryFile(suffix=".pydata", delete=False)
    temp_output.close()
    try:
        # Write a little temp batch file to set variables from batpath and
        # regurgitate them in a form we can parse.
        # First call batpath to update the cmd shell's environment. Then
        # use Python itself -- not just any Python interpreter, but THIS one
        # -- to format the ENTIRE environment into temp_output.name.
        temp_script_content = """\
call "%s"%s
"%s" -c "import os, pprint; pprint.pprint(os.environ)" > "%s"
""" % (batpath, ''.join(' '+arg for arg in args), sys.executable, temp_output.name)
        # Specify mode="w" for text mode ("\r\n" newlines); default is binary.
        with tempfile.NamedTemporaryFile(suffix=".cmd", delete=False, mode="w") as temp_script:
            temp_script.write(temp_script_content)
            temp_script_name = temp_script.name
        logger.debug("wrote to %s:\n%s" % (temp_script_name, temp_script_content))

        try:
            # Run our little batch script. Intercept any stdout it produces,
            # which would confuse our invoker, who wants to parse OUR stdout.
            cmdline = ['cmd', '/Q', '/C', temp_script_name]
            logger.debug(cmdline)
            script = subprocess.Popen(cmdline,
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            logger.debug(script.communicate()[0].rstrip())
            rc = script.wait()
            if rc != 0:
                raise SourceEnvError("%s failed with rc %s" % (' '.join(cmdline), rc))

        finally:
            # Whether or not the temporary script file worked, clean it up.
            os.remove(temp_script_name)

        # Read our temporary output file, knowing that it cannot contain any
        # output produced by batpath itself.
        with open(temp_output.name) as tf:
            raw_environ = tf.read()

    finally:
        # Clean up our temporary output file.
        os.remove(temp_output.name)

    try:
        # trust pprint.pprint() to produce output readable by ast.literal_eval()
        vsvars = literal_eval(raw_environ)
    except Exception:
        # but in case of a glitch, report raw string data for debugging
        logger.debug("pprint output of %s:\n%s" % (batpath, raw_environ))
        raise

    logger.debug("environment from %s:\n%s" % (batpath, pformat(vsvars)))
    return vsvars


def cygpath(*args):
    """run cygpath with specified command-line args, returning its output"""
    cmdline = ["cygpath"] + list(args)
    stdout = subprocess.Popen(cmdline, stdout=subprocess.PIPE) \
                       .communicate()[0].rstrip()
    logger.debug("%s => '%s'" % (cmdline, stdout))
    return stdout


environment_template = """
%(vars)s

    set_build_variables() {
        # set_build_variables is a dead branch of the evolutionary tree. The
        # functionality formerly engaged by the command:
        # set_build_variables convenience Release
        # has now been subsumed into autobuild source_environment itself. But
        # since a number of build-cmd.sh scripts have been tweaked to call
        # set_build_variables, make it produce an explanatory error. While it
        # would be simpler to remove the shell function and produce an error
        # that way, that could leave a developer scrambling to figure out:
        # okay, this line broke, why? Did set_build_variables go away? Did its
        # name change? What replaces it?
        echo "set_build_variables is no longer needed. Pass to autobuild source_environment
the pathname of your local clone of the build-variables/variables file, or set
AUTOBUILD_VARIABLES_FILE to that pathname before autobuild source_environment,
and remove the set_build_variables command. All the same variables will be set." 1>&2
        exit 1
    }

    fix_dylib_id() {
        local dylib=$1
        local dylink="$dylib"
        if [ -f "$dylib" ]; then
            if [ -L "$dylib" ]; then
                dylib="$(readlink "$dylib")"
            fi
            install_name_tool -id "@executable_path/../Resources/$dylib" "$dylib"
            if [ "$dylib" != "$dylink" ]; then
                ln -svf "$dylib" "$dylink"
            fi
        fi
    }
"""

if common.is_system_windows():
    windows_template = """
    USE_INCREDIBUILD=%(USE_INCREDIBUILD)d

    build_sln() {
        local solution=$1
        local config=$2
        local proj="${3:-}"

        if (($USE_INCREDIBUILD)) ; then
            BuildConsole "$solution" ${proj:+/PRJ="$proj"} /CFG="$config"
        else
            devenv.com "$(cygpath -w "$solution")" /build "$config" ${proj:+/project "$proj"}
        fi
    }

    # function for loading visual studio related env vars
    load_vsvars() {
%(vsvars)s
    }
    
    if ! (($USE_INCREDIBUILD)) ; then
        load_vsvars
    fi
    """
    environment_template = '\n'.join((environment_template, windows_template))


def do_source_environment(args):
    # OPEN-259: it turns out to be important that if AUTOBUILD is already set
    # in the environment, we should LEAVE IT ALONE. So if it exists, use the
    # existing value. Otherwise just use our own executable path.
    autobuild_path = common.get_autobuild_executable_path()
    AUTOBUILD = os.environ.get("AUTOBUILD", autobuild_path)
    var_mapping = {}
    # The cross-platform environment_template contains a generic 'vars' slot
    # where we can insert lines defining environment variables. Putting a
    # variable definition into this 'exports' dict causes it to be listed
    # there with an 'export' statement; putting a variable definition into the
    # 'vars' dict lists it there as local to that bash process. Logic just
    # before expanding environment_template populates 'exports' and 'vars'
    # into var_mapping["vars"]. We defer it that long so that conditional
    # logic below can, if desired, add to either 'exports' or 'vars' first.
    exports = dict(
        AUTOBUILD=AUTOBUILD,
        AUTOBUILD_VERSION_STRING=common.AUTOBUILD_VERSION_STRING,
        AUTOBUILD_PLATFORM=common.get_current_platform(),
        )
    vars = dict(
        MAKEFLAGS="",
##      DISTCC_HOSTS="",
        )

    # Let KeyError, if any, propagate: lack of AUTOBUILD_ADDRSIZE would be
    # an autobuild coding error. So would any value for that variable
    # other than what's stated below.
    exports["AUTOBUILD_CONFIGURE_ARCH"] = {
        '32': 'i386',
        '64': 'x86_64',
        }[os.environ["AUTOBUILD_ADDRSIZE"]]

    if common.is_system_windows():
        try:
            # reset stdout in binary mode so sh doesn't get confused by '\r'
            import msvcrt
            msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
        except ImportError:
            # cygwin gets a pass
            pass

        # load vsvars32.bat variables
        # *TODO - find a way to configure this instead of hardcoding default
        vs_ver = os.environ.get('AUTOBUILD_VSVER', '120')
        vsvars = load_vsvars(vs_ver)
        vsvarslist = []
        # We don't know which environment variables might be modified by
        # vsvars32.bat, but one of them is likely to be PATH. Treat PATH
        # specially: when a bash script invokes our load_vsvars() shell
        # function, we want to prepend to its existing PATH rather than
        # replacing it with whatever's visible to Python right now.
        try:
            PATH = vsvars.pop("PATH")
        except KeyError:
            pass
        else:
            # Translate paths from windows to cygwin format.
            # Match patterns of the form %SomeVar%. Match the SHORTEST such
            # string so that %var1% ... %var2% are two distinct matches.
            percents = re.compile(r"%(.*?)%")
            PATH = ":".join(
                # Some pathnames in the PATH var may be individually quoted --
                # strip quotes from those.
                # Moreover, some may have %SomeVar% substitutions; replace
                # with ${SomeVar} substitutions for bash. (Use curly braces
                # because we don't want to have to care what follows.)
                # may as well de-dup while we're at it
                dedup(cygpath("-u", percents.sub(r"${\1}", p.strip('"')))
                      for p in PATH.split(';'))
            )
            vsvarslist.append(("PATH", PATH + ":$PATH"))

        # Resetting our PROMPT is a bit heavy-handed. Plus the substitution
        # syntax probably differs.
        vsvars.pop("PROMPT", None)

        # Let KeyError, if any, propagate: lack of AUTOBUILD_ADDRSIZE would be
        # an autobuild coding error. So would any value for that variable
        # other than what's stated below.
        exports["AUTOBUILD_WIN_VSPLATFORM"] = {
            '32': 'Win32',
            '64': 'x64',
            }[os.environ["AUTOBUILD_ADDRSIZE"]]

        # When one of our build-cmd.sh scripts invokes CMake on Windows, it's
        # probably prudent to use a -G switch for the specific Visual Studio
        # version we want to target. It's not that uncommon for a Windows
        # build host to have multiple VS versions installed, and it can
        # sometimes take a while for us to switch to the newest release. Yet
        # we do NOT want to hard-code the version-specific CMake generator
        # name into each 3p source repo: we know from experience that
        # sprinkling version specificity throughout a large collection of 3p
        # repos is part of what makes it so hard to upgrade the compiler. The
        # problem is that the mapping from vs_ver to (e.g.) "Visual Studio 12"
        # isn't necessarily straightforward -- we may have to maintain a
        # lookup dict. That dict should not be replicated into each 3p repo,
        # it should be central. It should be here.
        try:
            AUTOBUILD_WIN_CMAKE_GEN = {
                '120': "Visual Studio 12",
                }[vs_ver]
        except KeyError:
            # We don't have a specific mapping for this value of vs_ver. Take
            # a wild guess. If we guess wrong, CMake will complain, and the
            # user will have to update autobuild -- which is no worse than
            # what s/he'd have to do anyway if we immediately produced an
            # error here. Plus this way, we defer the error until we hit a
            # build that actually consumes AUTOBUILD_WIN_CMAKE_GEN.
            AUTOBUILD_WIN_CMAKE_GEN = "Visual Studio %s" % (vs_ver[:-1])
        # Of course CMake also needs to know bit width :-P
        if os.environ["AUTOBUILD_ADDRSIZE"] == "64":
            AUTOBUILD_WIN_CMAKE_GEN += " Win64"
        exports["AUTOBUILD_WIN_CMAKE_GEN"] = AUTOBUILD_WIN_CMAKE_GEN

        # A pathname ending with a backslash (as many do on Windows), when
        # embedded in quotes in a bash script, might inadvertently escape the
        # close quote. Remove all trailing backslashes.
        for (k, v) in vsvars.iteritems():
            vsvarslist.append((k, v.rstrip('\\')))

        # may as well sort by keys
        vsvarslist.sort()

        # Since at coding time we don't know the set of all modified
        # environment variables, don't try to name them individually in the
        # template. Instead, bundle all relevant export statements into a
        # single substitution.
        var_mapping["vsvars"] = '\n'.join(
            ('        export %s="%s"' % varval for varval in vsvarslist)
        )

        try:
            use_ib = int(os.environ['USE_INCREDIBUILD'])
        except ValueError:
            logger.warning("USE_INCREDIBUILD environment variable contained garbage %r (expected 0 or 1)" % os.environ['USE_INCREDIBUILD'])
            use_ib = 0
        except KeyError:
            # We no longer require Incredibuild for Windows builds. Therefore,
            # if you want to engage Incredibuild, you must explicitly set
            # USE_INCREDIBUILD=1. We no longer implicitly set that if
            # BuildConsole.exe is on the PATH.
            use_ib = 0

        var_mapping.update(USE_INCREDIBUILD=use_ib)

    # Before expanding environment_template with var_mapping, finalize the
    # 'exports' and 'vars' dicts into var_mapping["vars"] as promised above.
    var_mapping["vars"] = '\n'.join(itertools.chain(
        (("    export %s='%s'" % (k, v)) for k, v in exports.iteritems()),
        (("    %s='%s'" % (k, v)) for k, v in vars.iteritems()),
        ))

    sys.stdout.write(environment_template % var_mapping)

    if get_params:
        # *TODO - run get_params.generate_bash_script()
        pass


def dedup(iterable):
    seen = set()
    for item in iterable:
        if item not in seen:
            seen.add(item)
            yield item


class AutobuildTool(autobuild_base.AutobuildBase):
    def get_details(self):
        return dict(name=self.name_from_file(__file__),
                    description='Prints out the shell environment Autobuild-based buildscripts to use (by calling \'eval\').')
    
    # called by autobuild to add help and options to the autobuild parser, and
    # by standalone code to set up argparse
    def register(self, parser):
        parser.description='prints out the shell environment Autobuild-based buildscripts to use (by calling \'eval\' i.e. eval "$(autobuild source_environment)").'
        parser.add_argument('-V', '--version', action='version',
                            version='source_environment tool module %s' % common.AUTOBUILD_VERSION_STRING)

    def run(self, args):
        do_source_environment(args)
