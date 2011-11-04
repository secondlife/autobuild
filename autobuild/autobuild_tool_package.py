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

import hashlib
import sys
import os
import tarfile
import time
import glob
import common
import logging
import configfile
import autobuild_base
from connection import SCPConnection, S3Connection
from common import AutobuildError
from zipfile import ZipFile, ZIP_DEFLATED


logger = logging.getLogger('autobuild.package')


class AutobuildTool(autobuild_base.AutobuildBase):
    def get_details(self):
        return dict(name=self.name_from_file(__file__),
                    description='Creates an archive of build output.')

    def register(self, parser):
        parser.description = "package the artifacts produced by the 'autobuild build' command into a package archive for distribution."
        parser.add_argument(
            '--config-file',
            default=configfile.AUTOBUILD_CONFIG_FILE,
            dest='autobuild_filename',
            help="the file used to describe how to build the package\n  (defaults to $AUTOBUILD_CONFIG_FILE or \"autobuild.xml\")")
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
        parser.add_argument(
            '--archive-format',
            default=None,
            dest='archive_format',
            help='the format of the archive (tbz2 or zip)')

    def run(self, args):
        config = configfile.ConfigurationDescription(args.autobuild_filename)
        package(config, args.platform, args.archive_filename, args.archive_format, args.check_license, args.dry_run)


class PackageError(AutobuildError):
    pass


def package(config, platform_name, archive_filename=None, archive_format=None, check_license=True, dry_run=False):
    """
    Create an archive for the given platform.
    """
    if not config.package_description:
        raise PackageError("no package description")
    package_description = config.package_description
    if not package_description.name:
        raise PackageError("no package name specified")
    # Not using logging, since this output should be produced unconditionally on stdout
    # Downstream build tools utilize this output
    print "packing %s" % package_description.name
    if not package_description.version:
        raise PackageError("no version number specified")
    build_directory = config.get_build_directory(platform_name)
    logger.info('packaging from %r' % build_directory)
    if not os.path.isdir(build_directory):
        raise PackageError("build directory %s is not a directory" % build_directory)
    logger.info("packaging from dir %s" % build_directory)
    platform_description = config.get_platform(platform_name)
    files = _get_file_list(platform_description, build_directory)
    if(platform_name != 'common'):
        try:
            files.extend(_get_file_list(config.get_platform('common'), build_directory))
        except configfile.ConfigurationError:
            pass # We don't have a common platform defined, that is ok.
    if check_license:
        _check_or_add_license(package_description, build_directory, files)
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
        for f in files:
            logger.info('added ' + f)
    else:
        archive_description = platform_description.archive
        format = _determine_archive_format(archive_format, archive_description)
        if format == 'tbz2':
            _create_tarfile(tarfilename + '.tar.bz2', build_directory, files)
        elif format == 'zip':
            _create_zip_archive(tarfilename + '.zip', build_directory, files)
        else:
            raise PackageError("archive format %s is not supported" % format)


def _determine_archive_format(archive_format_argument, archive_description):
    if archive_format_argument is not None:
        return archive_format_argument
    elif archive_description is None or archive_description.format is None:
        return 'tbz2'
    else:
        return archive_description.format


def _generate_archive_name(package_description, platform_name, suffix=''):
    # We ensure that the package name and platform definition
    # do not have hyphens in them as this will confuse the
    # related split_tarname() method.
    package_name = package_description.name.replace('-', '_')
    platform_name = platform_name.replace('/', '_').replace('-', '_')
    name = package_name + '-' + package_description.version + '-'
    name += platform_name + '-'
    name += time.strftime("%Y%m%d") + suffix
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


def _check_or_add_license(package_description, build_directory, filelist):
    if not package_description.license:
        raise PackageError("the license field is not specified")
    licensefile = package_description.license_file
    if not licensefile:
        licensefile = 'LICENSES/%s.txt' % package_description.name
    if licensefile.startswith('http://'):
        pass # No need to add.
    elif os.path.normcase(os.path.normpath(licensefile)) in \
             [os.path.normcase(os.path.normpath(f)) for f in filelist]:
        pass # Already found.
    elif os.path.isfile(os.path.join(build_directory, licensefile)):
        filelist.append(licensefile) # Can add to to the package.
    else:
        raise PackageError('cannot add license file %s' % licensefile)


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
                logger.info('added ' + file)
            except:
                raise PackageError("unable to add %s to %s" % (file, tarfilename))
        tfile.close()
    finally:
        os.chdir(current_directory)
    # Not using logging, since this output should be produced unconditionally on stdout
    # Downstream build tools utilize this output
    print "wrote  %s" % tarfilename
    _print_hash(tarfilename)
    
    
def _create_zip_archive(archive_filename, build_directory, file_list):
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
    print "wrote  %s" % archive_filename
    _print_hash(archive_filename)


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
    

def _print_hash(filename):
    fp = open(filename, 'rb')
    m = hashlib.md5()
    while True:
        d = fp.read(65536)
        if not d: break
        m.update(d)
    # Not using logging, since this output should be produced unconditionally on stdout
    # Downstream build tools utilize this output
    print "md5    %s" % m.hexdigest()    
    
