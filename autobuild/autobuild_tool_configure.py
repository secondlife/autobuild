"""
Configures source in preparation for building.
"""

import copy
import logging
import os

from autobuild import autobuild_base, common, configfile
from autobuild.autobuild_tool_source_environment import get_enriched_environment
from autobuild.build_id import establish_build_id
from autobuild.common import AutobuildError

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
        parser.add_argument('--id', '-i', dest='build_id', type=int, help='unique build number')
        parser.add_argument('additional_options', nargs="*", metavar='OPT',
                            help="an option to pass to the configuration command")

    def run(self, args):
        platform = common.get_current_platform()
        config = configfile.ConfigurationDescription(args.config_file)
        establish_build_id(args.build_id, config)
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


def _configure_a_configuration(config: configfile.BuildConfigurationDescription, build_configuration, extra_arguments, dry_run=False,
                               environment=None):
    try:
        common_build_configuration = \
            config.get_build_configuration(build_configuration.name, platform_name=common.PLATFORM_COMMON)
        common_configure = common_build_configuration.configure
    except Exception as e:
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
