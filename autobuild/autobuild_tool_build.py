"""
Builds the source for a package.
"""

import copy
import logging
import os
import re

import autobuild.scm.git
from autobuild import autobuild_base, common, configfile
from autobuild.autobuild_tool_configure import _configure_a_configuration
from autobuild.autobuild_tool_source_environment import get_enriched_environment
from autobuild.build_id import establish_build_id
from autobuild.common import AutobuildError, is_env_enabled

logger = logging.getLogger('autobuild.build')


# Add autobuild/bin to path.
os.environ["PATH"] = common.dedup_path(
    os.pathsep.join([os.environ["PATH"],
                     os.path.normpath(os.path.join(os.path.dirname(__file__), os.pardir, "bin"))]))


class BuildError(AutobuildError):
    pass

boolopt=re.compile("true$",re.I)

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
                            help="an option to pass to the build command")
        parser.add_argument('--all', '-a', dest='all', default=False, action="store_true",
                            help="build all configurations")
        parser.add_argument('--configuration', '-c', nargs='?', action="append", dest='configurations',
                            help="build a specific build configuration\n(may be specified as comma separated values in $AUTOBUILD_CONFIGURATION)",
                            metavar='CONFIGURATION',
                            default=self.configurations_from_environment())
        parser.add_argument('--id', '-i', dest='build_id', type=int, help='unique build number')

        parser.add_argument('--clean-only',
                            action="store_true",
                            default=True if 'AUTOBUILD_CLEAN_ONLY' in os.environ and boolopt.match(os.environ['AUTOBUILD_CLEAN_ONLY']) else False,
                            dest='clean_only',
                            help="require that the build not depend on packages that are local or lack metadata\n"
                            + "  may also be set by defining the environment variable AUTOBUILD_CLEAN_ONLY"
                            )
        parser.add_argument('--install-dir',
                            default=None,
                            dest='select_dir',          # see common.select_directories()
                            help='Where installed files were unpacked.')
        parser.add_argument('--installed-manifest',
                            default=configfile.INSTALLED_CONFIG_FILE,
                            dest='installed_filename',
                            help='The file used to record what is installed.')

    def run(self, args):
        platform = common.get_current_platform()
        config = configfile.ConfigurationDescription(args.config_file)
        build_id = establish_build_id(args.build_id, config)
        package_errors = configfile.check_package_attributes(config)

        if package_errors:
            raise BuildError(''.join((package_errors,
                                      "\n    in configuration ", args.config_file)))
        current_directory = os.getcwd()
        if args.clean_only:
            logger.info("building with --clean-only required")
        try:
            configure_first = not args.do_not_configure
            build_configurations = common.select_configurations(args, config, "building for")
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
                build_directory = bconfig.make_build_directory(
                    build_configuration, platform=platform, dry_run=args.dry_run)
                if not args.dry_run:
                    logger.debug("building in %s" % build_directory)
                    os.chdir(build_directory)
                else:
                    logger.info("building in %s" % build_directory)

                if configure_first:
                    result = _configure_a_configuration(bconfig, build_configuration,
                                                        args.build_extra_arguments, args.dry_run,
                                                        environment=environment)
                    if result != 0:
                        raise BuildError("configuring default configuration returned %d" % result)
                result = _build_a_configuration(bconfig, build_configuration,
                                                platform_name=platform,
                                                extra_arguments=args.build_extra_arguments,
                                                dry_run=args.dry_run,
                                                environment=environment)
                # always make clean copy of the build metadata regardless of result
                metadata_file_name = configfile.PACKAGE_METADATA_FILE
                logger.debug("metadata file name: %s" % metadata_file_name)
                if os.path.exists(metadata_file_name):
                    if not args.dry_run:
                        os.unlink(metadata_file_name)
                    else:
                        logger.info("would have replaced %s" % metadata_file_name)
                if result != 0:
                    raise BuildError("building configuration %s returned %d" %
                                     (build_configuration, result))

                # Create the metadata record for inclusion in the package
                metadata_file = configfile.MetadataDescription(path=metadata_file_name, create_quietly=True)
                # COPY the package description from the configuration: we're
                # going to convert it to metadata format.
                metadata_file.package_description = \
                    configfile.PackageDescription(bconfig.package_description)
                # A metadata package_description has a version attribute
                # instead of a version_file attribute.
                if config.package_description.use_scm_version:
                    try:
                        metadata_file.package_description.version = \
                            metadata_file.package_description.read_scm_version(build_directory)
                    except LookupError:
                        raise BuildError(
                            'use_scm_version specified in autobuild.xml but no version found in source control (git).'
                        )
                else:
                    if 'version_file' not in metadata_file.package_description:
                        raise BuildError('No version_file specified in autobuild.xml.')
                    metadata_file.package_description.version = \
                        metadata_file.package_description.read_version_file(build_directory)
                    del metadata_file.package_description["version_file"]
                logger.info("built %s version %s" %
                            (metadata_file.package_description.name,
                             metadata_file.package_description.version))
                metadata_file.package_description.platforms = None  # omit data on platform configurations
                metadata_file.platform = platform
                metadata_file.configuration = build_configuration.name
                metadata_file.build_id = build_id

                if common.is_env_enabled('AUTOBUILD_VCS_INFO'):
                    git = autobuild.scm.git.new_client(build_directory)
                    if git:
                        metadata_file.package_description.vcs_branch = os.environ.get("AUTOBUILD_VCS_BRANCH", git.branch)
                        metadata_file.package_description.vcs_revision = os.environ.get("AUTOBUILD_VCS_REVISION", git.revision)
                        metadata_file.package_description.vcs_url = os.environ.get("AUTOBUILD_VCS_URL", git.url)
                    else:
                        logger.warning("Unable to initialize git. Repository not found or git CLI not available")

                # get the record of any installed packages
                logger.debug("installed files in " + args.installed_filename)

                # SL-773: This if/else partly replicates
                # common.select_directories() because our build_directory
                # comes from bconfig, which has been $-expanded.
                # The former select_directories() call produced (e.g.)
                # build-vc120-$AUTOBUILD_ADDRSIZE, which didn't exist.
                if args.select_dir:
                    install_dir = args.select_dir
                    logger.debug("specified metadata directory: {}"
                                 .format(install_dir))
                else:
                    # packages were written into 'packages' subdir of build directory by default
                    install_dir = os.path.join(build_directory, "packages")
                    logger.debug("metadata in build subdirectory: {}"
                                 .format(install_dir))

                # load the list of already installed packages
                installed_pathname = os.path.realpath(
                    os.path.join(install_dir, args.installed_filename))
                if os.path.exists(installed_pathname):
                    metadata_file.add_dependencies(installed_pathname)
                else:
                    logger.debug("no installed files found (%s)" % installed_pathname)
                if args.clean_only and metadata_file.dirty:
                    raise BuildError("Build depends on local or legacy installables\n"
                               +"  use 'autobuild install --list-dirty' to see problem packages\n"
                               +"  rerun without --clean-only to allow building anyway")
                if not args.dry_run:
                    metadata_file.save()
        finally:
            os.chdir(current_directory)


def _build_a_configuration(config, build_configuration,
                           platform_name=common.get_current_platform(),
                           extra_arguments=[], dry_run=False,
                           environment={}):
    try:
        common_build_configuration = \
            config.get_build_configuration(build_configuration.name, platform_name=common.PLATFORM_COMMON)
        parent_build = common_build_configuration.build
    except Exception as e:
        if logger.getEffectiveLevel() <= logging.DEBUG:
            logger.exception(e)
        logger.debug('no common platform found')
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
    logger.info('executing build command:\n  %s', build_executable.__str__(extra_arguments))
    if not dry_run:
        return build_executable(extra_arguments, environment=environment)
    else:
        return 0
