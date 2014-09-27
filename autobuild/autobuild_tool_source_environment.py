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

    vsvars_path = os.path.join(VSxxxCOMNTOOLS, "vsvars32.bat")
    # Invent a temp filename into which to capture our script output. Some
    # versions of vsvars32.bat emit stdout, some don't; we've been bitten both
    # ways. Bypass that by not commingling our desired output into stdout.
    temp_output = tempfile.NamedTemporaryFile(suffix=".pydata", delete=False)
    temp_output.close()
    try:
        # Write a little temp batch file to suck in vsvars32.bat and regurgitate
        # its contents in a form we can parse.
        # First call vsvars32.bat to update the cmd shell's environment. Then
        # use Python itself -- not just any Python interpreter, but THIS one
        # -- to format the ENTIRE environment into temp_output.name.
        temp_script_content = """\
call "%s"
"%s" -c "import os, pprint; pprint.pprint(os.environ)" > "%s"
""" % (vsvars_path, sys.executable, temp_output.name)
        # Specify mode="w" for text mode ("\r\n" newlines); default is binary.
        with tempfile.NamedTemporaryFile(suffix=".cmd", delete=False, mode="w") as temp_script:
            temp_script.write(temp_script_content)
            temp_script_name = temp_script.name
        logger.debug("wrote to %s:\n%s" % (temp_script_name, temp_script_content))

        try:
            # This stanza should be irrelevant these days because we make a
            # point of avoiding cygwin Python exactly because of pathname
            # compatibility problems. Retain it, though, just in case it's
            # saving somebody's butt.
            if sys.platform == "cygwin":
                # cygwin needs the file to have executable permissions
                os.chmod(temp_script_name, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)
                # and translated to a path name that cmd.exe can understand
                temp_script_name = cygpath("-d", temp_script_name)

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
        # output produced by vsvars32.bat itself.
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
        logger.debug("pprint output of vsvars32:\n" + raw_environ)
        raise

    logger.debug("environment from vsvars32:\n" + pformat(vsvars))

    # Now weed out of vsvars anything identical to OUR environment. Retain
    # only environment variables actually modified by vsvars32.bat.
    # Use items() rather than iteritems(): capture the list of items up front
    # instead of trying to traverse vsvars while modifying it.
    for var, value in vsvars.items():
        # Bear in mind that some variables were introduced by vsvars32.bat and
        # are therefore NOT in our os.environ.
        if os.environ.get(var) == value:
            # Any environment variable from our batch script that's identical
            # to our own os.environ was simply inherited. Discard it.
            del vsvars[var]
    logger.debug("set by vsvars32:\n" + pformat(vsvars))

    return vsvars


def cygpath(*args):
    """run cygpath with specified command-line args, returning its output"""
    cmdline = ["cygpath"] + list(args)
    stdout = subprocess.Popen(cmdline, stdout=subprocess.PIPE) \
                       .communicate()[0].rstrip()
    logger.debug("%s => '%s'" % (cmdline, stdout))
    return stdout


environment_template = """
    # disable verbose debugging output (maybe someday we'll want to make this configurable with -v ?)
    restore_xtrace="$(set +o | grep xtrace)"
    set +o xtrace

    export AUTOBUILD="%(AUTOBUILD_EXECUTABLE_PATH)s"
    export AUTOBUILD_VERSION_STRING="%(AUTOBUILD_VERSION_STRING)s"
    export AUTOBUILD_PLATFORM="%(AUTOBUILD_PLATFORM)s"

    fail() {
        echo "BUILD FAILED"
        if [ -n "$PARABUILD_BUILD_NAME" ] ; then
            # if we're running under parabuild then we have to clean up its stuff
            finalize false "$@"
        else
            exit 1
        fi
    }
    pass() {
        echo "BUILD SUCCEEDED"
        succeeded=true
    }

    # imported build-lindenlib functions
    fetch_archive() {
        local url=$1
        local archive=$2
        local md5=$3
        if ! [ -r "$archive" ] ; then
            curl -L -o "$archive" "$url"                    || return 1
        fi
        if [ "$AUTOBUILD_PLATFORM" = "darwin" ] ; then
            test "$md5 $archive" = "$(md5 -r "$archive")"
        else
            echo "$md5 *$archive" | md5sum -c
        fi
    }
    extract() {
        # Use a tar command appropriate to the extension of the filename passed as
        # $1. If a subsequent update of a given tarball changes compression types,
        # this should hopefully avoid having to go through this script to update
        # the tar switches to correspond to the new file type.
        switch="-x"
        # Decide whether to specify -xzvf or -xjvf based on whether the archive
        # name ends in .tar.gz or .tar.bz2.
        case "$1" in
        *.tar.gz|*.tgz)
            gzip -dc "$1" | tar -xf -
            ;;
        *.tar.bz2|*.tbz2)
            bzip2 -dc "$1" | tar -xf -
            ;;
        *.zip)
            unzip -q "$1"
            ;;
        *)
            echo "Do not know how to extract $1" 1>&2
            return 1
            ;;
        esac
    }
    calc_md5() {
        local archive=$1
        local md5_cmd=md5sum
        if [ "$AUTOBUILD_PLATFORM" = "darwin" ] ; then
            md5_cmd="md5 -r"
        fi
        $md5_cmd "$archive" | cut -d ' ' -f 1
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

    MAKEFLAGS="%(MAKEFLAGS)s"
    #DISTCC_HOSTS="%(DISTCC_HOSTS)s"

    $restore_xtrace
"""

if common.get_current_platform() == "windows":
    windows_template = """
    # disable verbose debugging output
    set +o xtrace

    USE_INCREDIBUILD=%(USE_INCREDIBUILD)d
    build_vcproj() {
        local vcproj=$1
        local config=$2

        if (($USE_INCREDIBUILD)) ; then
            BuildConsole "$vcproj" /CFG="$config"
        else
            devenv "$vcproj" /build "$config"
        fi
    }

    build_sln() {
        local solution=$1
        local config=$2
        local proj=$3

        if (($USE_INCREDIBUILD)) ; then
            if [ -z "$proj" ] ; then
                BuildConsole "$solution" /CFG="$config"
            else
                BuildConsole "$solution" /PRJ="$proj" /CFG="$config"
            fi
        else
            if [ -z "$proj" ] ; then
                devenv.com "$(cygpath -m "$solution")" /build "$config"
            else
                devenv.com "$(cygpath -m "$solution")" /build "$config" /project "$proj"
            fi
        fi
    }

    # function for loading visual studio related env vars
    load_vsvars() {
%(vsvars)s
    }
    
    if ! (($USE_INCREDIBUILD)) ; then
        load_vsvars
    fi

    $restore_xtrace
    """
    environment_template = '\n'.join((environment_template, windows_template))


def do_source_environment(args):
    # OPEN-259: it turns out to be important that if AUTOBUILD is already set
    # in the environment, we should LEAVE IT ALONE. So if it exists, use the
    # existing value. Otherwise, everywhere but Windows, just use our own
    # executable path. On Windows (sigh), the function returns a pathname we
    # can use internally -- but since source_environment is specifically for
    # feeding a bash shell, twiddle that pathname for cygwin bash.
    autobuild_path = common.get_autobuild_executable_path()
    AUTOBUILD = os.environ.get("AUTOBUILD",
                               autobuild_path if common.get_current_platform() != "windows"
                               else ("$(cygpath -u '%s')"% autobuild_path))
    var_mapping = {'AUTOBUILD_EXECUTABLE_PATH': AUTOBUILD,
                   'AUTOBUILD_VERSION_STRING': common.AUTOBUILD_VERSION_STRING,
                   'AUTOBUILD_PLATFORM': common.get_current_platform(),
                   'MAKEFLAGS': "",
                   'DISTCC_HOSTS': "",
                   }

    if common.get_current_platform() == "windows":
        try:
            # reset stdout in binary mode so sh doesn't get confused by '\r'
            import msvcrt
            msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
        except ImportError:
            # cygwin gets a pass
            pass

        # load vsvars32.bat variables
        # *TODO - find a way to configure this instead of hardcoding default
        vs_ver = os.environ.get('AUTOBUILD_VSVER', '100')
        vsvars = load_vsvars(vs_ver)
        exports = []
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
            exports.append(("PATH", PATH + ":$PATH"))

        # Resetting our PROMPT is a bit heavy-handed. Plus the substitution
        # syntax probably differs.
        vsvars.pop("PROMPT", None)

        # A pathname ending with a backslash (as many do on Windows), when
        # embedded in quotes in a bash script, might inadvertently escape the
        # close quote. Remove all trailing backslashes.
        for (k, v) in vsvars.iteritems():
            exports.append((k, v.rstrip('\\')))

        # may as well sort by keys
        exports.sort()

        # Since at coding time we don't know the set of all modified
        # environment variables, don't try to name them individually in the
        # template. Instead, bundle all relevant export statements into a
        # single substitution.
        var_mapping["vsvars"] = '\n'.join(
            ('        export %s="%s"' % varval for varval in exports)
        )

        try:
            use_ib = int(os.environ['USE_INCREDIBUILD'])
        except ValueError:
            logger.warning("USE_INCREDIBUILD environment variable contained garbage %r (expected 0 or 1)" % os.environ['USE_INCREDIBUILD'])
            use_ib = 0
        except KeyError:
            use_ib = int(bool(common.find_executable('BuildConsole')))

        var_mapping.update(USE_INCREDIBUILD=use_ib)

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
