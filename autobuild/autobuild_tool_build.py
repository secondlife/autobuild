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
Builds the source for a package.
"""

import os
import sys

# autobuild modules:
import common
import copy
import autobuild_base
import configfile
import logging
from common import AutobuildError
from autobuild_tool_configure import configure
from autobuild_tool_configure import _configure_a_configuration


logger = logging.getLogger('autobuild.build')


# Add autobuild/bin to path.
os.environ["PATH"] = os.pathsep.join([os.environ["PATH"], os.path.normpath(
    os.path.join(os.path.dirname(__file__), os.pardir, "bin"))])


class BuildError(AutobuildError):
    pass
    

class AutobuildTool(autobuild_base.AutobuildBase):
    def get_details(self):
        return dict(name=self.name_from_file(__file__),
                    description="Builds platform targets.")

    def register(self, parser):
        parser.usage = """%(prog)s [-h] [--no-configure] [--config-file CONFIG_FILE] [-a]
                       [-c CONFIGURATION] [--dry-run] -- [OPT [OPT ...]]"""
        parser.description = "build the current package and copy its output artifacts into the build directory for use by the 'autobuild package' command."
        parser.add_argument('--config-file',
            dest='config_file',
            default=configfile.AUTOBUILD_CONFIG_FILE,
            help='(defaults to $AUTOBUILD_CONFIG_FILE or "autobuild.xml")')
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
                            help="build a specific build configuration\n(may be specified as comma separated values in $AUTOBUILD_CONFIGURATION)",
                            metavar='CONFIGURATION',
                            default=self.configurations_from_environment())
        parser.add_argument('--use-cwd', dest='use_cwd', default=False, action="store_true",
            help="build in current working directory")

    def run(self, args):
        config = configfile.ConfigurationDescription(args.config_file)
        current_directory = os.getcwd()
        build_directory = config.make_build_directory()
        logger.debug("building in %s" % build_directory)
        if not args.use_cwd:
            os.chdir(build_directory)
        try:
            configure_first = not args.do_not_configure
            if args.all:
                build_configurations = config.get_all_build_configurations()
            elif args.configurations:
                build_configurations = \
                    [config.get_build_configuration(name) for name in args.configurations]
            else:
                build_configurations = config.get_default_build_configurations()
            if not build_configurations:
                logger.warn("no applicable build configurations found, autobuild cowardly refuses to build nothing!")
                logger.warn("did you remember to mark a build command as default? try passing 'default=true' to your 'autobuild edit build' command")

            logger.debug("building for configuration(s) %r" % build_configurations)
            for build_configuration in build_configurations:
                if configure_first:
                    result = _configure_a_configuration(config, build_configuration,
                        args.build_extra_arguments, args.dry_run)
                    if result != 0:
                        raise BuildError("configuring default configuration returned %d" % (result))                    
                result = _build_a_configuration(config, build_configuration,
                    args.build_extra_arguments, args.dry_run)
                if result != 0:
                    raise BuildError("building default configuration returned %d" % (result))
        finally:
            os.chdir(current_directory)


def build(config, build_configuration_name, extra_arguments=[]):
    """
    Execute the platform build command for the named build configuration.

    A special 'common' platform may be defined which can provide parent commands for the build
    command using the inheritence mechanism described in the 'executable' package.  The
    working platform's build configuration will be matched to the build configuration in common with
    the same name if it exists.  To be built, a build configuration must be defined in the working
    platform though it does not need to contain any actual commands if it is desired that the common
    commands be used.  Build configurations defined in the common platform but not the working
    platform are not built.
    """
    build_configuration = config.get_build_configuration(build_configuration_name)
    return _build_a_configuration(config, build_configuration, extra_arguments)


def _build_a_configuration(config, build_configuration, extra_arguments, dry_run=False):
    try:
        common_build_configuration = \
            config.get_build_configuration(build_configuration.name, 'common')
        parent_build = common_build_configuration.build
    except:
        parent_build = None
    if build_configuration.build is not None:
        build_executable = copy.copy(build_configuration.build)
        build_executable.parent = parent_build
    elif parent_build is not None:
        logger.info('no build executable defined; falling back to parent')
        build_executable = parent_build
    else:
        logger.info('no build executable defined; doing nothing')
        return 0
    logger.info('executing build command %s', build_executable.__str__(extra_arguments))
    if not dry_run:
        return build_executable(extra_arguments, common.get_autobuild_environment())
    else:
        return 0
