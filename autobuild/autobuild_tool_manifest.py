#!/usr/bin/env python
# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$


import os

import autobuild_base
from common import get_current_platform, AutobuildError
import configfile


def construct_manifest(packageInfo, patterns, platform):
    """
    Creates the manifest in the package info structure for the given platform using the provided 
    patterns.
    """
    packageInfo.set_manifest_files(platform, patterns)    
    
    
class autobuild_tool(autobuild_base.autobuild_base):
    def get_details(self):
        return dict(name=self.name_from_file(__file__),
            description="Add manifest entries to the autobuild configuration file using the"
            " provided patterns.")
     
    def register(self, parser):
        parser.add_argument('-v', '--version', action='version', version='manifest tool 1.0')
        parser.add_argument('-f','--file',
            help="The configuration file to modify")
        parser.add_argument('pattern', nargs='+',
            help='File pattern to match when searching for files to add to the manifest')
        parser.add_argument('-p','--package',
            help="The package to which this manifest should be added")
        parser.add_argument('--platform', default=get_current_platform(),
            help="The platform associated with this manifest")
        parser.add_argument('--verbose', action='store_true')

    def run(self, args):
        config = configfile.ConfigFile()
        if args.file is not None:
            config.load(args.file)
        else:
             config.load()
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


class DefaultPackageUndefinedError(AutobuildError):
	pass


class UnkownPackageError(AutobuildError):
	pass


if __name__ == "__main__":
    sys.exit( autobuild_tool().main( sys.argv[1:] ) )
