# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$

"""
Autobuild sub-command to build the source for a package.
"""

import os
import shlex
import subprocess
import sys

# autobuild modules:
import common
import autobuild_base
import configfile
from common import AutobuildError

class autobuild_tool(autobuild_base.autobuild_base):
    def get_details(self):
        return dict(name=self.name_from_file(__file__),
                    description='Runs the package\'s build command')

    def register(self, parser):
        parser.add_argument('--config-file',
            dest='config_file',
            default=configfile.BUILD_CONFIG_FILE,
            help="")
        parser.add_argument('--build-extra-args',
            dest='build_extra_args',
            default='',
            help="extra arguments to the build command, will be split on any whitespace boundaries but obeys quotations")

    def run(self, args):
        cf = configfile.ConfigFile()
        cf.load(args.config_file)
        package_definition = cf.package_definition

        build_command = package_definition.build_command(common.get_current_platform())
        if not build_command:
            raise AutobuildError("No build command specified in config file.")

        build_command = shlex.split(build_command) + shlex.split(args.build_extra_args)

        # Tease out command itself.
        prog = build_command[0]
        # Is it a simple filename, or does it have a path attached? If it's
        # got a path, assume user knows what s/he's doing and just use it. But
        # if it's a simple filename, perform a path search. This isn't quite
        # the same as the search that would be performed by subprocess.call():
        # for a command 'foo', our search will find 'foo.cmd', which empirically
        # does NOT happen with subprocess.call().
        if os.path.basename(prog) == prog:
            # Because autobuild itself now provides certain convenience
            # scripts for use as config-file build commands, ensure that
            # autobuild/bin is available in our PATH.
            bin = os.path.normpath(os.path.join(os.path.dirname(__file__), os.pardir, "bin"))
            pathdirs = os.environ.get("PATH", "").split(os.pathsep)
            os.environ["PATH"] = os.pathsep.join(pathdirs + [bin, '.'])

            # Search (augmented) PATH for the command. Replace it into the
            # whole command line.
            foundprog = common.find_executable(prog, os.path.splitext(prog)[1])
            if not foundprog:
                raise AutobuildError("Cannot find command %s in the path." % prog)
            build_command[0] = foundprog

        print "in %r:\nexecuting: %s" % (os.getcwd(), ' '.join(repr(a) for a in build_command))
        # *TODO - be careful here, we probably want to sanitize the environment further.
        build_env = dict(os.environ, AUTOBUILD=common.get_autobuild_executable_path())
        subprocess.call(build_command, env=build_env)
