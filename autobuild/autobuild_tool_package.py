# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$

"""
Creates archives of build output.

The package sub-command works by locating all of the files in the
build output directory that match the manifest specified in the
configuration file. The manifest can include platform-specific and
platform-common files, and they can use glob-style wildcards.

The package command optionally enforces the restriction that a license
string and a valid licensefile for the package has been specified. The operation
will be aborted in this is not the case.

In summary, the package command requires that you have specified the
following metadata in the autobuild.xml file:

* build_directory
* manifest
* version
* license
* license_file (assumes LICENSES/<package-name>.txt otherwise)
"""

import sys
import os
import tarfile
import time
import glob
import common
import configfile
import autobuild_base
from connection import SCPConnection, S3Connection
from common import AutobuildError


class AutobuildTool(autobuild_base.AutobuildBase):
    def get_details(self):
        return dict(name=self.name_from_file(__file__),
                    description='Creates an archive of build output.')

    def register(self, parser):
        parser.add_argument(
            '--config-file',
            default=configfile.AUTOBUILD_CONFIG_FILE,
            dest='autobuild_filename',
            help='the file used to describe how to build the package')
        parser.add_argument(
            '--archive-name',
            default=None,
            dest='archive_filename',
            help='the filename of the archive that autobuild will create')
        parser.add_argument(
            '-p', '--platform', 
            default=common.get_current_platform(),
            dest='platform',
            help='override the working platform')
        parser.add_argument(
            '--skip-license-check', 
            action='store_false',
            default=True,
            dest='check_license',
            help="do not perform the license check")

    def run(self, args):
        config = configfile.ConfigurationDescription(args.autobuild_filename)
        package(config, args.platform, args.archive_filename, args.check_license, args.dry_run)


class PackageError(AutobuildError):
    pass


def package(config, platform_name, archive_filename=None, check_license=True, dry_run=False):
    """
    Create an archive for the given platform.
    """
    if not config.package_description:
        raise PackageError("no package description")
    package_description = config.package_description
    if not package_description.version:
        raise PackageError("no version number specified")
    build_directory = config.get_build_directory(platform_name)
    if not os.path.isdir(build_directory):
        PackageError("build directory %s is not a directory" % build_directory)
    platform_description = config.get_platform(platform_name)
    files = _get_file_list(platform_description, build_directory)
    if(platform_name != 'common'):
        files.extend(_get_file_list(config.get_platform('common'), build_directory))
    if check_license:
        if not _check_license(package_description, build_directory, files):
            raise PackageError('failed licence check')
    config_directory = os.path.dirname(config.path)
    if not archive_filename:
        tardir = config_directory
        tarname = _generate_archive_name(package_description, platform_name)
        tarfilename = os.path.join(tardir, tarname)
    elif os.path.isabs(archive_filename):
        tarfilename = archive_filename
    else:
        tarfilename = os.path.abs(os.path.join(config_directory, archive_filename))
    if dry_run:
        for file in files:
            print "Adding (dry-run)", file
        print "Dry-run: would have created %s" % tarfilename
    else:
        _create_tarfile(tarfilename, build_directory, files)


def _generate_archive_name(package_description, platform_name, suffix=''):
    # We ensure that the package name and platform definition
    # do not have hyphens in them as this will confuse the
    # related split_tarname() method.
    package_name = package_description.name.replace('-', '_')
    platform_name = platform.replace('/', '_').replace('-', '_')
    name = package_name + '-' + package_description.version + '-'
    name += platform_name + '-'
    name += time.strftime("%Y%m%d") + suffix
    name += '.tar.bz2'
    return name


def _get_file_list(platform_description, build_directory):
    if not platform_description.manifest:
        return []
    files = []
    current_directory = os.getcwd()
    os.chdir(build_directory)
    try:
        for pattern in platform_description.manifest:
            files.extend(glob.glob(pattern))
    finally:
        os.chdir(current_directory)
    return files


def _check_license(package_description, build_directory, filelist):
    if not package_description.license:
        raise PackageError("the license field is not specified")
    licensefile = package_description.license_file
    if not licensefile:
        licensefile = 'LICENSES/%s.txt' % package_description.name
    if licensefile.startswith('http://'):
        return True
    for file in filelist:
        # use os.path.normpath for windows os.pathsep compatibility
        if os.path.normpath(licensefile) == os.path.normpath(file):
            return True
    return False


def _create_tarfile(tarfilename, build_directory, filelist):
    if not os.path.exists(os.path.dirname(tarfilename)):
        os.makedirs(os.path.dirname(tarfilename))
    current_directory = os.getcwd()
    os.chdir(build_directory)
    try:
        tfile = tarfile.open(tarfilename, 'w:bz2')
        for file in filelist:
            try:
                tfile.add(file)
            except:
                raise PackageError("unable to add %s to %s" % (file, tarfilename))
        tfile.close()
    finally:
        os.chdir(current_directory)
