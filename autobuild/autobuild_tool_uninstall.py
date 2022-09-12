"""
Uninstall binary packages.

This autobuild sub-command will read an installed-packages.xml file and
uninstall the packages specified on the command line from the install
directory.
"""

import logging
import os

from autobuild import autobuild_base, common, configfile
from autobuild.autobuild_tool_install import uninstall
from autobuild.autobuild_tool_source_environment import get_enriched_environment

logger = logging.getLogger('autobuild.uninstall')


class UninstallError(common.AutobuildError):
    pass

__help = """\
This autobuild command uninstalls package files.

The command will remove the packages specified on the command line from the
installed-packages.xml file, and delete every file originally
installed by that archive.
"""


def uninstall_packages(options, installed_filename, args, dry_run):
    # load the list of already installed packages
    logger.debug("loading " + installed_filename)
    installed_file = configfile.Dependencies(installed_filename)

    for package in args:
        if not dry_run:
            uninstall(package, installed_file)
        else:
            logger.info("would have uninstalled %s" % package)

    # update the installed-packages.xml file
    if not dry_run:
        installed_file.save()
    return 0


# define the entry point to this autobuild tool
class AutobuildTool(autobuild_base.AutobuildBase):
    def get_details(self):
        return dict(name=self.name_from_file(__file__),
                    description='Uninstall package archives.')

    def register(self, parser):
        parser.description = "uninstall artifacts installed by the 'autobuild install' command."
        parser.add_argument('package',
                            nargs='*',
                            help='List of packages to uninstall.')
        # Sigh, the ONLY reason we need to read the autobuild.xml file is to
        # find the default --install-dir.
        parser.add_argument('--config-file',
                            default=configfile.AUTOBUILD_CONFIG_FILE,
                            dest='install_filename',
                            help="The file used to describe what should be installed\n  (defaults to $AUTOBUILD_CONFIG_FILE or \"autobuild.xml\").")
        parser.add_argument('--installed-manifest',
                            default=configfile.INSTALLED_CONFIG_FILE,
                            dest='installed_filename',
                            help='The file used to record what is installed.')
        # The only reason we need to know --install-dir is because the default
        # --installed-manifest is relative.
        parser.add_argument('--install-dir',
                            default=None,
                            dest='select_dir',          # see common.select_directories()
                            help='Where to find the default --installed-manifest file.')
        parser.add_argument('--all', '-a',
                            dest='all',
                            default=False,
                            action="store_true",
                            help="uninstall packages for all configurations")
        parser.add_argument('--configuration', '-c',
                            nargs='?',
                            action="append",
                            dest='configurations',
                            help="uninstall packages for a specific build configuration\n(may be specified as comma separated values in $AUTOBUILD_CONFIGURATION)",
                            metavar='CONFIGURATION',
                            default=self.configurations_from_environment())

    def run(self, args):
        platform=common.get_current_platform()
        logger.debug("uninstalling for platform "+platform)

        installed_filename = args.installed_filename
        if os.path.isabs(installed_filename):
            installed_filenames = [installed_filename]
        else:
            # This logic handles the (usual) case when installed_filename is
            # relative to install_dir. Therefore we must figure out install_dir.

            # write packages into 'packages' subdir of build directory by default
            config = configfile.ConfigurationDescription(args.install_filename)
            # establish a build directory so that the install directory is relative to it
            build_configurations = common.select_configurations(args, config, "uninstalling for")
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
                build_configuration = bconfig.get_build_configuration(build_configuration.name, platform_name=platform)
                build_directory = bconfig.get_build_directory(build_configuration, platform_name=platform)
                logger.debug("build directory: %s" % build_directory)
                installed_filenames = \
                  [os.path.realpath(os.path.join(install_dir, installed_filename))
                   for install_dir in
                   common.select_directories(args, config,
                                            "install", "uninstalling",
                                            lambda cnf:
                                            os.path.join(build_directory,
                                                         "packages"))]

        logger.debug("installed filenames: %s" % installed_filenames)
        for installed_filename in installed_filenames:
            uninstall_packages(args, installed_filename, args.package, args.dry_run)
