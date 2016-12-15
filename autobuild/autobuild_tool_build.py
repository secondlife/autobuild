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
import re
import logging
import copy

# autobuild modules:
import common
import autobuild_base
import configfile
from common import AutobuildError
from autobuild_tool_configure import _configure_a_configuration
from autobuild_tool_source_environment import get_enriched_environment


logger = logging.getLogger('autobuild.build')


# Add autobuild/bin to path.
os.environ["PATH"] = os.pathsep.join([os.environ["PATH"], os.path.normpath(
    os.path.join(os.path.dirname(__file__), os.pardir, "bin"))])


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
        parser.add_argument('--id', '-i', dest='build_id', help='unique build identifier')

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
        build_id = common.establish_build_id(args.build_id)  # sets id (even if not specified),
                                                             # and stores in the AUTOBUILD_BUILD_ID environment variable
        config = configfile.ConfigurationDescription(args.config_file)
        package_errors = \
            configfile.check_package_attributes(config,
                                                additional_requirements=['version_file'])
        if package_errors:
            # Now that we've deprecated hard-coded version and started
            # requiring version_file instead, provide an explanation when it's
            # missing, instead of confounding a longtime autobuild user with
            # failure to meet a brand-new requirement.
            # Recall that package_errors isa str that also has an attrs
            # attribute. Only emit the verbose message if version_file is
            # actually one of the problematic attributes, and the config file
            # had to be converted from an earlier file format, and the
            # original file format version predates version_file.
            # (missing orig_ver attribute means a current autobuild.xml, which
            # is why we pass get() a default value that bypasses verbose)
            # (version_file was introduced at AUTOBUILD_CONFIG_VERSION 1.3)
            if "version_file" in package_errors.attrs \
            and common.get_version_tuple(config.get("orig_ver", "1.3")) < (1, 3):
                verbose = """
New requirement: instead of stating a particular version number in the %(xml)s
file, we now require you to configure a version_file attribute. This should be
the path (relative to the build_directory) of a small text file containing
only the package version string. Freezing the version number into %(xml)s
means we often forget to update it there. Reading the version number from a
separate text file allows your build script to create that file from data
available in the package. version_file need not be in the manifest; it's used
only by 'autobuild build' to create package metadata.
""" % dict(xml=configfile.AUTOBUILD_CONFIG_FILE)
            else:
                verbose = ""
            # Now, regardless of the value of 'verbose', show the message.
            raise BuildError(''.join((package_errors,
                                      "\n    in configuration ", args.config_file,
                                      verbose)))
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

            # packages were written into 'packages' subdir of build directory by default
            install_dirs = common.select_directories(
                args, config, "metadata", "getting installed packages",
                lambda cnf: os.path.join(config.get_build_directory(cnf, platform), "packages"))

            # get the absolute paths to the install dir and installed-packages.xml file
            install_dir = os.path.realpath(install_dirs[0])

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
                # get the record of any installed packages
                logger.debug("installed files in " + args.installed_filename)
                # load the list of already installed packages
                installed_pathname = os.path.join(install_dir, args.installed_filename)
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
    except Exception, e:
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
