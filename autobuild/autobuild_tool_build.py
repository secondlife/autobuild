# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$

"""
Autobuild sub-command to build the source for a package.
"""

import os
import sys

# autobuild modules:
import common
import copy
import autobuild_base
import configfile
from common import AutobuildError
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
        parser.add_argument('--all','-a',dest='all', default=False, action="store_true",
            help="build all configurations")
        parser.add_argument('--configuration', '-c', nargs='?', action="append", dest='configurations', 
            help="build a specific build configuration", metavar='CONFIGURATION')
        parser.usage = """%(prog)s [-h] [--no-configure] [--config-file CONFIG_FILE] [-a]
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
            if args.all:
                build_configurations = config.get_all_build_configurations()
            elif args.configurations is not None:
                build_configurations = \
                    [config.get_build_configuration(name) for name in args.configurations]
            else:
                build_configurations = config.get_default_build_configurations()
            for build_configuration in build_configurations:
                if configure_first:
                    result = _configure_a_configuration(config, build_configuration,
                        args.build_extra_arguments)
                    if result != 0:
                        raise BuildError("configuring default configuration returned '%d'" % (result))                    
                result = _build_a_configuration(config, build_configuration, args.build_extra_arguments)
                if result != 0:
                    raise BuildError("building default configuration returned '%d'" % (result))
        finally:
            os.chdir(current_directory)


def build(config, build_configuration_name, extra_arguments=[]):
    """
    Execute the platform build command for the named build configuration.
    """
    build_configuration = config.get_build_configuration(build_configuration_name)
    return _build_a_configuration(config, build_configuration, extra_arguments)


def _build_a_configuration(config, build_configuration, extra_arguments):
    try:
        common_build_configuration = \
            config.get_build_configuration(build_configuration.name, 'common')
        parent_build = common_build_configuration.build
    except:
        parent_build = None
    if build_configuration.build is not None:
        build_executable = copy.copy(build_configuration.build)
        build_executable.parent = parent_build
        return build_executable(extra_arguments)
    elif parent_build is not none:
        return parent_build(extra_arguments)
    else:
        return 0
