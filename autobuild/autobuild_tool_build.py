# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$

"""
Autobuild sub-command to build the source for a package.
"""

import copy
import os
import shlex
import subprocess
import sys

# autobuild modules:
import common
import autobuild_base
import configfile
from common import AutobuildError
from executable import Executable
from autobuild_tool_configure import configure
from autobuild_tool_configure import _configure_a_configuration


# Add autobuild/bin to path.
os.environ["PATH"] = os.pathsep.join([os.environ["PATH"], os.path.normpath(
    os.path.join(os.path.dirname(__file__), os.pardir, "bin"))])


class BuildError(AutobuildError):
    pass
    

class autobuild_tool(autobuild_base.autobuild_base):
    def get_details(self):
        return dict(name=self.name_from_file(__file__),
                    description="Builds platform targets.")

    def register(self, parser):
        parser.add_argument('--config-file',
            dest='config_file',
            default=configfile.AUTOBUILD_CONFIG_FILE,
            help="")
        parser.add_argument('--no-configure',
            dest='do_not_configure',
            default=False,
            action="store_true",
            help="do not configure before building")
        parser.add_argument('build_extra_arguments', nargs="*", metavar='OPT',
            help="an option to pass to the build command" )
        parser.add_argument('--configuration', '-c', nargs='?', action="append", dest='configurations', 
            help="build a specific build configuration", metavar='CONFIGURATION')
        parser.usage = """%(prog)s [-h] [--no-configure] [--config-file CONFIG_FILE] 
                       [-c CONFIGURATION] [--dry-run] -- [OPT [OPT ...]]"""

    def run(self, args):
        if args.dry_run:
            return
        config = configfile.ConfigurationDescription(args.config_file)
        current_directory = os.getcwd()
        build_directory = config.make_build_directory()
        os.chdir(build_directory)
        try:
            configure_first = not args.do_not_configure
            if args.configurations is not None:
                for build_configuration_name in args.configurations:
                    if configure_first:
                        result = configure.configure(config, build_configuration_name, 
                            args.build_extra_arguments)
                        if result != 0:
                            raise BuildError("configuring configuration '%s' returned '%d'" % 
                                (build_configuration_name, result))
                    result = build(config, build_configuration_name, args.build_extra_arguments)
                    if result != 0:
                        raise BuildError("building configuration '%s' returned '%d'" % 
                            (build_configuration_name, result))
            else:
                for build_configuration in config.get_default_build_configurations():
                    if configure_first:
                        result = _configure_a_configuration(build_configuration,
                            args.build_extra_arguments)
                        if result != 0:
                            raise BuildError("configuring default configuration returned '%d'" % (result))                    
                    result = _build_a_configuration(build_configuration, args.build_extra_arguments)
                    if result != 0:
                        raise BuildError("building default configuration returned '%d'" % (result))
        finally:
            os.chdir(current_directory)


def build(config, build_configuration_name, extra_arguments=[]):
    """
    Execute the platform build command for the named build configuration.
    """
    build_configuration = config.get_build_configuration(build_configuration_name)
    return _build_a_configuration(build_configuration, extra_arguments)


def _build_a_configuration(build_configuration, extra_arguments):
    if build_configuration.build is not None:
        return build_configuration.build(extra_arguments)
    else:
        return 0
