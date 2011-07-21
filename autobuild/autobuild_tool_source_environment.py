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
import shutil
import stat
import subprocess
import sys
import tempfile
import logging

import common
import autobuild_base

from llbase import llsd

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
        pass
    # *TODO - restore original sys.path value

def load_vsvars(vsver):
    vsvars_path = os.path.join(os.environ["VS%sCOMNTOOLS" % vsver], "vsvars32.bat")
    temp_script_name = tempfile.mktemp(suffix=".cmd")

    shutil.copy(vsvars_path, temp_script_name)
    # append our little llsd+notation bit to the end
    temp_script_file = open(temp_script_name, "a")
    temp_script_file.write("""
        echo {
        echo "VSPATH":"%PATH%",
        echo "VSINCLUDE":"%INCLUDE%",
        echo "VSLIB":"%LIB%",
        echo "VSLIBPATH":"%LIBPATH%",
        echo }
    """)
    temp_script_file.close()

    if sys.platform == "cygwin":
        # cygwin needs the file to have executable permissions, and translated to a path
        # name that cmd.exe can understand
        cmdline = ["cygpath", "-d", "%s" % temp_script_name]
        logger.debug(cmdline)
        os.chmod(temp_script_name, stat.S_IREAD|stat.S_IWRITE|stat.S_IEXEC)
        (temp_script_name, _) = subprocess.Popen(cmdline, stdout=subprocess.PIPE).communicate()
        temp_script_name = temp_script_name.rstrip()

    cmdline = ['cmd', '/Q', '/C', temp_script_name]
    logger.debug(cmdline)
    cmd = subprocess.Popen(cmdline, stdout=subprocess.PIPE)
    (cmdout, cmderr) = cmd.communicate()

    logger.debug("cmdout: %r" % cmdout)

    os.remove(temp_script_name)

    # *HACK
    # slice off the 1st line ("Setting environment for using..." preamble)
    cmdout = '\n'.join(cmdout.split('\n')[1:])
    # escape backslashes
    cmdout = '\\\\'.join(cmdout.split('\\'))

    vsvars = llsd.parse(cmdout)

    logger.debug("VSVARS: %r" % vsvars)

    # translate paths from windows to cygwin format
    vsvars['VSPATH'] = ":".join(
        ['"$(cygpath -u \'%s\')"' % p for p in vsvars['VSPATH'].split(';') ]
    )

    # fix for broken builds on windows (don't let anything escape the closing quote)
    for (k,v) in vsvars.iteritems():
        vsvars[k] = v.rstrip('\\')

    return vsvars

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

if common.get_current_platform() is "windows":
    windows_template = """
    # disable verbose debugging output
    set +o xtrace

    USE_INCREDIBUILD=%(USE_INCREDIBUILD)d
    build_vcproj() {
        local vcproj=$1
        local config=$2

        if ((%(USE_INCREDIBUILD)d)) ; then
            BuildConsole "$vcproj" /CFG="$config"
        else
            devenv "$vcproj" /build "$config"
        fi
    }

    build_sln() {
        local solution=$1
        local config=$2
        local proj=$3

        if ((%(USE_INCREDIBUILD)d)) ; then
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
        export PATH=%(VSPATH)s:"$PATH"
        export INCLUDE="%(VSINCLUDE)s"
        export LIB="%(VSLIB)s"
        export LIBPATH="%(VSLIBPATH)s"
    }
    
    if ! ((%(USE_INCREDIBUILD)d)) ; then
        load_vsvars
    fi

    $restore_xtrace
    """
    environment_template = "%s\n%s" % (environment_template, windows_template)

def do_source_environment(args):
    var_mapping = {
            'AUTOBUILD_EXECUTABLE_PATH':common.get_autobuild_executable_path(),
            'AUTOBUILD_VERSION_STRING':common.AUTOBUILD_VERSION_STRING,
            'AUTOBUILD_PLATFORM':common.get_current_platform(),
            'MAKEFLAGS':"",
            'DISTCC_HOSTS':"",
        }

    if common.get_current_platform() is "windows":
        try:
            # reset stdout in binary mode so sh doesn't get confused by '\r'
            import msvcrt
            msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
        except ImportError:
            # cygwin gets a pass
            pass

        # load vsvars32.bat variables
        # *TODO - find a way to configure this instead of hardcoding to vc80
        try:
            vs_ver = os.environ['AUTOBUILD_VSVER']
        except KeyError:
            vs_ver = "100"
            
        var_mapping.update(load_vsvars(vs_ver))
        var_mapping.update(AUTOBUILD_EXECUTABLE_PATH=("$(cygpath -u '%s')" % common.get_autobuild_executable_path()))

        try:
            use_ib = int(os.environ['USE_INCREDIBUILD'])
        except ValueError:
            logger.warning("USE_INCREDIBUILD environment variable contained garbage %r (expected 0 or 1), turning incredibuild off" % os.environ['USE_INCREDIBUILD'])
            use_ib = 0
        except KeyError:
            use_ib = int(bool(common.find_executable('BuildConsole')))

        var_mapping.update(USE_INCREDIBUILD=use_ib)

    sys.stdout.write(environment_template % var_mapping)

    if get_params:
        # *TODO - run get_params.generate_bash_script()
        pass

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

