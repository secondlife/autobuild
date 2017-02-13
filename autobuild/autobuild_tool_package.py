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
Creates archives of build output.

The package sub-command works by locating all of the files in the
build output directory that match the manifest specified in the
configuration file. The manifest can include platform-specific and
platform-common files which may use glob-style wildcards.

The package command optionally enforces the restriction that a license
string and a valid license_file for the package has been specified. The operation
will be aborted in this is not the case.

In summary, the package command requires that you have specified the
following metadata in the autobuild.xml file:

* build_directory
* manifest
* version_file
* license
* license_file (assumes LICENSES/<package-name>.txt otherwise)
"""

import hashlib
import os
import tarfile
import getpass
import glob
import subprocess
import urllib2
import re
from zipfile import ZipFile, ZIP_DEFLATED

import common
import logging
import configfile
import autobuild_base
from common import AutobuildError

logger = logging.getLogger('autobuild.package')

#
# Talking to remote servers
#
boolopt=re.compile("true$",re.I)

class AutobuildTool(autobuild_base.AutobuildBase):
    def get_details(self):
        return dict(name=self.name_from_file(__file__),
                    description='Creates an archive of build output.')

    def register(self, parser):
        parser.description = "package the artifacts produced by the 'autobuild build' command into a package archive for distribution."
        parser.add_argument('--config-file',
                            default=configfile.AUTOBUILD_CONFIG_FILE,
                            dest='autobuild_filename',
                            help="the file used to describe how to build the package\n  (defaults to $AUTOBUILD_CONFIG_FILE or \"autobuild.xml\")")
        parser.add_argument('--archive-name',
                            default=None,
                            dest='archive_filename',
                            help='the filename of the archive that autobuild will create')
        parser.add_argument('--skip-license-check',
                            action='store_false',
                            default=False,
                            dest='check_license',
                            help="(deprecated - now has no effect)")
        parser.add_argument('--archive-format',
                            default=None,
                            dest='archive_format',
                            help='the format of the archive (tbz2 or zip)')
        parser.add_argument('--build-dir',
                            default=None,
                            dest='select_dir',  # see common.select_directories()
                            help='Package specific build directory.')
        parser.add_argument('--all', '-a',
                            action="store_true",
                            default=False,
                            dest='all',
                            help="package all configurations")
        parser.add_argument('--clean-only',
                            action="store_true",
                            default=True if 'AUTOBUILD_CLEAN_ONLY' in os.environ and boolopt.match(os.environ['AUTOBUILD_CLEAN_ONLY']) else False,
                            dest='clean_only',
                            help="require that the package not depend on installables that are local or lack metadata\n"
                            + "  may also be set by defining the environment variable AUTOBUILD_CLEAN_ONLY"
                            )
        parser.add_argument('--list-depends',
                            action="store_true",
                            default=False,
                            dest='list_depends',
                            help="return success if the package contains no dependencies that either are local or lack metadata")
        parser.add_argument('--configuration', '-c', nargs='?', action="append", dest='configurations', 
                            help="package a specific build configuration\n(may be specified as comma separated values in $AUTOBUILD_CONFIGURATION)",
                            metavar='CONFIGURATION',
                            default=self.configurations_from_environment())
        parser.add_argument('--results-file',
                            default=None,
                            dest='results_file',
                            help="file name in which to write results as shell variable assignments")

    def run(self, args):
        logger.debug("loading " + args.autobuild_filename)
        platform=common.get_current_platform()
        if args.clean_only:
            logger.info("packaging with --clean-only required")
        if args.check_license:
            logger.warning("The --skip-license-check option is deprecated; it now has no effect")
        if args.results_file and os.path.exists(args.results_file):
            if args.dry_run:
                logger.info("would have removed previous results: %s" % args.results_file)
            else:
                logger.debug("clearing previous results: %s" % args.results_file)
                os.remove(args.results_file)
        config = configfile.ConfigurationDescription(args.autobuild_filename)

        build_dirs = common.select_directories(args, config, "build", "packaging",
                                               lambda cnf:
                                               config.get_build_directory(cnf, platform))

        if not build_dirs:
            build_dirs = [config.get_build_directory(None, platform)]
        is_clean = True
        for build_dir in build_dirs:
            package(config, build_dir, platform, archive_filename=args.archive_filename,
                    archive_format=args.archive_format, clean_only=args.clean_only, results_file=args.results_file, dry_run=args.dry_run)


class PackageError(AutobuildError):
    pass


def package(config, build_directory, platform_name, archive_filename=None, archive_format=None, clean_only=False, results_file=None, dry_run=False):
    """
    Create an archive for the given platform.
    Returns True if the archive is not dirty, False if it is
    """
    if not config.package_description:
        raise PackageError("no package description")
    package_description = config.package_description
    if not package_description.name:
        raise PackageError("no package name specified in configuration")
    if not package_description.license:
        raise PackageError("no license specified in configuration")
    ##  autobuild.xml's version_file is validated by build subcommand.
    ##  By this time we should only have to validate metadata package version;
    ##  this happens a few lines down, after reading metadata_file.
    if not os.path.isdir(build_directory):
        raise PackageError("build directory %s is not a directory" % build_directory)
    logger.info("packaging from %s" % build_directory)
    platform_description = config.get_platform(platform_name)
    files = set()
    missing = []
    files, missing = _get_file_list(platform_description, build_directory)
    if platform_name != common.PLATFORM_COMMON:
        try:
            common_files, common_missing = _get_file_list(config.get_platform(common.PLATFORM_COMMON), build_directory)
            files |= common_files
            missing.extend(common_missing)
        except configfile.ConfigurationError:
            pass  # We don't have a common platform defined, that is ok.
    if missing:
        raise PackageError("No files matched manifest specifiers:\n"+'\n'.join(missing))

    # add the manifest files to the metadata file (list does not include itself)
    metadata_file_name = configfile.PACKAGE_METADATA_FILE
    logger.debug("metadata file name: %s" % metadata_file_name)
    metadata_file_path = os.path.abspath(os.path.join(build_directory, metadata_file_name))
    metadata_file = configfile.MetadataDescription(path=metadata_file_path)
    if metadata_file.dirty:
        if clean_only:
            raise PackageError("Package depends on local or legacy installables\n"
                               "  use 'autobuild install --list-dirty' to see problem packages\n"
                               "  rerun without --clean-only to allow packaging anyway")
        else:
            logger.warning("WARNING: package depends on local or legacy installables\n"
                           "  use 'autobuild install --list-dirty' to see problem packages")
    if not getattr(metadata_file.package_description,'version',None):
        raise PackageError("no version in metadata package_description -- "
                           "please verify %s version_file and rerun build" %
                           os.path.basename(config.path))
    if package_description.license_file:
        if package_description.license_file not in files:
            files.add(package_description.license_file)
    if 'source_directory' in metadata_file.package_description:
        del metadata_file.package_description['source_directory']
    disallowed_paths=[path for path in files if ".." in path or os.path.isabs(path)]
    if disallowed_paths:
        raise PackageError("Absolute paths or paths with parent directory elements are not allowed:\n  "+"\n  ".join(sorted(disallowed_paths))+"\n")
    metadata_file.manifest = files
    if metadata_file.build_id:
        build_id = metadata_file.build_id
    else:
        raise PackageError("no build_id in metadata - rerun build\n"
                           "  you may specify (--id <id>) or let it default to the date")
    if metadata_file.platform != platform_name:
        raise PackageError("build platform (%s) does not match current platform (%s)"
                           % (metadata_file.platform, platform_name))

    # printing unconditionally on stdout for backward compatibility
    # the Linden Lab build scripts no longer rely on this
    # (they use the --results-file option instead)
    print "packing %s" % package_description.name

    results = None
    if not dry_run:
        if results_file:
            try:
                results=open(results_file,'wb')
            except IOError, err:
                raise PackageError("Unable to open results file %s:\n%s" % (results_file, err))
            results.write('autobuild_package_name="%s"\n' % package_description.name)
            results.write('autobuild_package_clean="%s"\n' % ("false" if metadata_file.dirty else "true"))
            results.write('autobuild_package_metadata="%s"\n' % metadata_file_path)
        metadata_file.save()

    # add the metadata file name to the list of files _after_ putting that list in the metadata
    files.add(metadata_file_name)

    config_directory = os.path.dirname(config.path)
    if not archive_filename:
        tardir = config_directory
        tarname = _generate_archive_name(metadata_file.package_description, build_id, platform_name)
        tarfilename = os.path.join(tardir, tarname)
    elif os.path.isabs(archive_filename):
        tarfilename = archive_filename
    else:
        tarfilename = os.path.abspath(os.path.join(config_directory, archive_filename))
    logger.debug(tarfilename)
    if dry_run:
        for f in files:
            logger.info('would have added: ' + f)
    else:
        archive_description = platform_description.archive
        format = _determine_archive_format(archive_format, archive_description)
        if format == 'tbz2':
            _create_tarfile(tarfilename + '.tar.bz2', build_directory, files, results)
        elif format == 'zip':
            _create_zip_archive(tarfilename + '.zip', build_directory, files, results)
        else:
            raise PackageError("archive format %s is not supported" % format)
    if not dry_run and results:
        results.close()
    return not metadata_file.dirty

def _determine_archive_format(archive_format_argument, archive_description):
    if archive_format_argument is not None:
        return archive_format_argument
    elif archive_description is None or archive_description.format is None:
        return 'tbz2'
    else:
        return archive_description.format


def _generate_archive_name(package_description, build_id, platform_name, suffix=''):
    # We ensure that the package name and platform definition
    # do not have hyphens in them as this will confuse the
    # related split_tarname() method.
    package_name = package_description.name.replace('-', '_')
    platform_name = platform_name.replace('/', '_').replace('-', '_')
    name = package_name \
           + '-' + package_description.version \
           + '-' + platform_name \
           + '-' + build_id \
           + suffix
    return name


def _get_file_list(platform_description, build_directory):
    files = set()
    missing = []
    if platform_description.manifest:
        current_directory = os.getcwd()
        os.chdir(build_directory)
        try:
            for pattern in platform_description.manifest:
                found = glob.glob(pattern)
                if not found:
                    missing.append(pattern)
                for found_file in found:
                    files.add(found_file)
        finally:
            os.chdir(current_directory)
    return [files, missing]

def _create_tarfile(tarfilename, build_directory, filelist, results):
    if not os.path.exists(os.path.dirname(tarfilename)):
        os.makedirs(os.path.dirname(tarfilename))
    current_directory = os.getcwd()
    os.chdir(build_directory)
    try:
        tfile = tarfile.open(tarfilename, 'w:bz2')
        for file in filelist:
            try:
                # Make sure permissions are set on Windows.
                if common.is_system_windows():
                    command = ["CACLS", file, "/T", "/G", getpass.getuser() + ":F"]
                    CACLS = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    output = CACLS.communicate("Y")[0]
                    rc = CACLS.wait()
                    if rc != 0:
                        print "error: rc %s from %s:" % (rc, ' '.join(command))
                    print output
                tfile.add(file)
                logger.info('added ' + file)
            except (tarfile.TarError, IOError), err:
                # IOError in case the specified filename can't be opened
                raise PackageError("unable to add %s to %s: %s" % (file, tarfilename, err))
        tfile.close()
    finally:
        os.chdir(current_directory)
    # printing unconditionally on stdout for backward compatibility
    # the Linden Lab build scripts no longer rely on this
    # (they use the --results-file option instead)
    print "wrote  %s" % tarfilename
    if results:
        results.write('autobuild_package_filename="%s"\n' % tarfilename)
    _print_hash(tarfilename, results)


def _create_zip_archive(archive_filename, build_directory, file_list, results):
    if not os.path.exists(os.path.dirname(archive_filename)):
        os.makedirs(os.path.dirname(archive_filename))
    current_directory = os.getcwd()
    os.chdir(build_directory)
    try:
        archive = ZipFile(archive_filename, 'w', ZIP_DEFLATED)
        added_files = set()
        for file in file_list:
            _add_file_to_zip_archive(archive, file, archive_filename, added_files)
        archive.close()
    finally:
        os.chdir(current_directory)
    # printing unconditionally on stdout for backward compatibility
    # the Linden Lab build scripts no longer rely on this
    # (they use the --results-file option instead)
    print "wrote  %s" % archive_filename
    if results:
        results.write('autobuild_package_filename="%s"\n' % archive_filename)
    _print_hash(archive_filename, results)


def _add_file_to_zip_archive(zip_file, unnormalized_file, archive_filename, added_files):
    # Normalize the path that actually gets added to zipfile.
    file = os.path.normpath(unnormalized_file)
    # But normalize case only for testing added_files.
    lowerfile = os.path.normcase(file)
    if lowerfile in added_files:
        logger.info('skipped duplicate ' + file)
        return
    added_files.add(lowerfile)
    if os.path.isdir(file):
        for f in os.listdir(file):
            _add_file_to_zip_archive(zip_file, os.path.join(file, f), archive_filename, added_files)
    else:
        try:
            zip_file.write(file)
        except Exception, err:
            raise PackageError("%s: unable to add %s to %s: %s" %
                               (err.__class__.__name__, file, archive_filename, err))
        logger.info('added ' + file)


def _print_hash(filename, results):
    fp = open(filename, 'rb')
    m = hashlib.md5()
    while True:
        d = fp.read(65536)
        if not d:
            break
        m.update(d)
    # printing unconditionally on stdout for backward compatibility
    # the Linden Lab build scripts no longer rely on this
    # (they use the --results-file option instead)
    print "md5    %s" % m.hexdigest()
    if results:
        results.write('autobuild_package_md5="%s"\n' % m.hexdigest())

    # Not using logging, since this output should be produced unconditionally on stdout
    # Downstream build tools utilize this output

