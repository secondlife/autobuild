#!/usr/bin/env python
# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$


import autobuild_base
from common import get_current_platform, AutobuildError
import configfile
import fnmatch
import os
import os.path as path
import re


def construct_manifest(packageInfo, patterns, platform):
    """
    Adds all files under the packages build directory into the package info's platform manifest 
    which match at least one of the filename patterns in the provided list.
    """
    if packageInfo.builddir is None:
        raise BuildDirectoryUnspecified("no build directory specified for this package")
    root = path.expandvars(packageInfo.builddir);
    data = {'root':root,'patterns':patterns,'files':[]}
    path.walk(root, _collect_manifest_files, data)
    packageInfo.set_manifest_files(platform, data['files'])    
    
    
class autobuild_tool(autobuild_base.autobuild_base):
    def get_details(self):
        return dict(name=self.name_from_file(__file__),
            description="Add manifest entries to the autobuild configuration file by recursively "
            "searching all directories under the root directory for files matching the provided "
            "patterns.")
     
    def register(self, parser):
        parser.add_argument('-v', '--version', action='version', version='manifest tool 1.0')
        parser.add_argument('pattern', nargs='+',
            help='File pattern to match when searching for files to add to the manifest')
        parser.add_argument('-p','--package',
            help="The package to which this manifest should be added")
        parser.add_argument('--platform', default=get_current_platform(),
            help="The platform associated with this manifest")
        parser.add_argument('--verbose', action='store_true')

    def run(self, args):
        config = configfile.ConfigFile()
        config.load();
        if args.package:
            packageInfo = config.package(args.package)
            if packageInfo is None:
                raise UnkownPackageError("package '%s' not found" % args.package)
        elif config.package_definition is not None:
            packageInfo = config.package_definition
        else:
            raise DefaultPackageUndefinedError("default package not defined")
        construct_manifest(packageInfo, args.pattern, args.platform)
        if args.verbose or args.dry_run:
            for file in packageInfo.manifest_files(args.platform):
                print file
        if args.dry_run is not None and not args.dry_run:
            config.save()


class BuildDirectoryUnspecified(AutobuildError):
    pass


class DefaultPackageUndefinedError(AutobuildError):
	pass


class UnkownPackageError(AutobuildError):
	pass


def _collect_manifest_files(data, dirname, files):
    directory = re.sub(data['root'], '', dirname)
    for file in files:
        filepath = path.normpath(path.join(directory, file))
        for pattern in data['patterns']:
            if fnmatch.fnmatch(filepath, pattern):
                 data['files'].append(filepath)
                 break


if __name__ == "__main__":
    sys.exit( autobuild_tool().main( sys.argv[1:] ) )
