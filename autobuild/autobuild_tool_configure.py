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
from autobuild_tool_source_environment import get_enriched_environment
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
        parser.add_argument('--all', '-a', dest='all', default=False, action="store_true",
                            help="build all configurations")
        parser.add_argument('--id', '-i', dest='build_id', help='unique build identifier')
        parser.add_argument('additional_options', nargs="*", metavar='OPT',
                            help="an option to pass to the configuration command")

    def run(self, args):
        platform=common.get_current_platform()
        common.establish_build_id(args.build_id)  # sets id (even if not specified),
                                                  # and stores in the AUTOBUILD_BUILD_ID environment variable
        config = configfile.ConfigurationDescription(args.config_file)
        package_errors = configfile.check_package_attributes(config)
        if package_errors:
            raise ConfigurationError("%s\n    in configuration %s" \
                                     % (package_errors, args.config_file))
        current_directory = os.getcwd()
        try:
            build_configurations = common.select_configurations(args, config, "configuring for")
            if not build_configurations:
                logger.error("no applicable configurations found.\n"
                             "did you remember to mark a configuration as default?\n"
                             "autobuild cowardly refuses to do nothing!")

            for build_configuration in build_configurations:
                # Get enriched environment based on the current configuration
                environment = get_enriched_environment(build_configuration.name)
                # then get a copy of the config specific to this build
                # configuration
                bconfig = config.copy()
                # and expand its $variables according to the environment.
                bconfig.expand_platform_vars(environment)
                # Re-fetch the build configuration so we have its expansions.
                build_configuration = bconfig.get_build_configuration(
                    build_configuration.name, platform_name=platform)
                build_directory = bconfig.make_build_directory(
                    build_configuration, platform=platform, dry_run=args.dry_run)
                if not args.dry_run:
                    logger.debug("configuring in %s" % build_directory)
                    os.chdir(build_directory)
                else:
                    logger.info("configuring in %s" % build_directory)
                result = _configure_a_configuration(bconfig, build_configuration,
                                                    args.additional_options, args.dry_run,
                                                    environment=environment)
                if result != 0:
                    raise ConfigurationError("default configuration returned %d" % result)
        finally:
            os.chdir(current_directory)

## nat 2016-12-01: As far as I can tell, this function is completely unused.
## If I'm wrong, we'll uncomment it and life goes on. If I'm right, I'll get
## rid of it next time I maintain this module for any reason.
##def configure(config, build_configuration_name, extra_arguments=[], environment={}):
##    """
##    Execute the platform configure command for the named build configuration.
##
##    The special 'common' platform may be defined which can provide parent commands for the configure 
##    command using the inheritence mechanism described in the 'executable' package.  The working
##    platform's build configuration will be matched to the build configuration in common with the
##    same name if it exists.  To be configured, a build configuration must be defined in the working
##    platform though it does not need to contain any actual commands if it is desired that the common
##    commands be used.  Build configurations defined in the common platform but not the working
##    platform are not configured.
##    """
##    build_configuration = config.get_build_configuration(build_configuration_name, platform)
##    return _configure_a_configuration(config, build_configuration, extra_arguments,
##                                      environment)


def _configure_a_configuration(config, build_configuration, extra_arguments, dry_run=False,
                               environment={}):
    try:
        common_build_configuration = \
            config.get_build_configuration(build_configuration.name, platform_name=common.PLATFORM_COMMON)
        common_configure = common_build_configuration.configure
    except Exception, e:
        if logger.getEffectiveLevel() <= logging.DEBUG:
            logger.exception(e)
        logger.debug('no common platform found')
        common_configure = None

    # see if the specified configuration exists; if so, use it
    if build_configuration.configure is not None:
        configure_executable = copy.copy(build_configuration.configure)
        configure_executable.parent = common_configure 

    # if the specified configuration doesn't exist, and common does, use common
    elif common_configure is not None:
        configure_executable = common_configure

    else:
        logger.info('no configure executable defined; doing nothing')
        return 0

    logger.info('configure command:\n  %s', configure_executable.__str__(extra_arguments))
    if not dry_run:
        return configure_executable(extra_arguments, environment=environment)
    else:
        return 0
