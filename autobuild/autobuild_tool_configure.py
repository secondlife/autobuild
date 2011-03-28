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
Configures source in preparation for building.
"""

import autobuild_base
import copy
import common
from common import AutobuildError
import configfile
import os
import logging


logger = logging.getLogger('autobuild.configure')


class ConfigurationError(AutobuildError):
    pass


class AutobuildTool(autobuild_base.AutobuildBase):
    def get_details(self):
        return dict(name='configure',
            description="Configures platform targets.")
     
    def register(self, parser):
        parser.usage = "%(prog)s [-h] [--dry-run] [-c CONFIGURATION][-a][--config-file FILE] [-- OPT [OPT ...]]"
        parser.description = "configure the build directory to prepare for either the 'autobuild build' command or a manual build. (not all packages will require this step)"
        parser.add_argument('--config-file',
            dest='config_file',
            default=configfile.AUTOBUILD_CONFIG_FILE,
            help='(defaults to $AUTOBUILD_CONFIG_FILE or "autobuild.xml")')
        parser.add_argument('--configuration', '-c', nargs='?', action="append", dest='configurations', 
                            help="build a specific build configuration\n(may be specified as comma separated values in $AUTOBUILD_CONFIGURATION)",
                            metavar='CONFIGURATION',
                            default=self.configurations_from_environment())
        parser.add_argument('--all','-a',dest='all', default=False, action="store_true",
            help="build all configurations")
        parser.add_argument('additional_options', nargs="*", metavar='OPT',
            help="an option to pass to the configuration command" )
        parser.add_argument('--use-cwd', dest='use_cwd', default=False, action="store_true",
            help="configure in current working directory")

    def run(self, args):
        config = configfile.ConfigurationDescription(args.config_file)
        current_directory = os.getcwd()
        build_directory = config.make_build_directory()
        logger.debug("configuring in %s" % build_directory)
        if not args.use_cwd:
            os.chdir(build_directory)
        try:
            if args.all:
                build_configurations = config.get_all_build_configurations()
            elif args.configurations:
                build_configurations = \
                    [config.get_build_configuration(name) for name in args.configurations]
            else:
                build_configurations = config.get_default_build_configurations()
            logger.debug("configuring for configuration(s) %r" % build_configurations)
            for build_configuration in build_configurations:
                result = _configure_a_configuration(config, build_configuration,
                    args.additional_options, args.dry_run)
                if result != 0:
                    raise ConfigurationError("default configuration returned %d" % (result))
        finally:
            os.chdir(current_directory)

def configure(config, build_configuration_name, extra_arguments=[]):
    """
    Execute the platform configure command for the named build configuration.

    A special 'common' platform may be defined which can provide parent commands for the configure 
    command using the inheritence mechanism described in the 'executable' package.  The working
    platform's build configuration will be matched to the build configuration in common with the
    same name if it exists.  To be configured, a build configuration must be defined in the working
    platform though it does not need to contain any actual commands if it is desired that the common
    commands be used.  Build configurations defined in the common platform but not the working
    platform are not configured.
    """
    build_configuration = config.get_build_configuration(build_configuration_name)
    return _configure_a_configuration(config, build_configuration, extra_arguments)


def _configure_a_configuration(config, build_configuration, extra_arguments, dry_run=False):
    try:
        common_build_configuration = \
            config.get_build_configuration(build_configuration.name, 'common')
        parent_configure = common_build_configuration.configure
    except Exception, e:
        if logger.getEffectiveLevel() <= logging.DEBUG:
            logger.exception(e)
        logger.debug('no common platform found')
        parent_configure = None
    if build_configuration.configure is not None:
        configure_executable = copy.copy(build_configuration.configure)
        configure_executable.parent = parent_configure
    elif parent_configure is not None:
        configure_executable = parent_configure
    else:
        logger.info('no configure executable defined; doing nothing')
        return 0
    logger.info('executing configure command %s', configure_executable.__str__(extra_arguments))
    if not dry_run:
        return configure_executable(extra_arguments, common.get_autobuild_environment())
    else:
        return 0
