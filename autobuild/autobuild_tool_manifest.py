# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$


import autobuild_base
from common import get_current_platform
import configfile
import fnmatch
import os
import os.path as path
import re
	

class autobuild_tool(autobuild_base.autobuild_base):
    def get_details(self):
        return dict(name='manifest', 
            description="Adds manifest entries to the autobuild configuration file by recursively "
            "searching all directories under the root directory for files matching the provided "
            "patterns.")
     
    def register(self, parser):
        parser.add_argument('-v', '--version', action='version', version='manifest tool 1.0')
        parser.add_argument('patterns', nargs='+',
            help='File patterns to match when searching for files to add to the manifest')
        parser.add_argument('-p','--package',
            help="The package to which this manifest should be added")
        parser.add_argument('--platform', default=get_current_platform(),
            help="The platform associated with this manifest")
        parser.add_argument('-r','--rootdir', default=os.getcwd(),
            help="Root directory below which to search for manifest files")
        parser.add_argument('--verbose', action='store_true')

    def run(self, args):
        config = configfile.ConfigFile()
        config.load();
        if args.package:
            packageInfo = config.package(args.package)
        elif config.package_count is 1:
            packageInfo = config.package(config.package_names.next())
        elif config.package_count > 1:
            raise PackageSelectionAmbiguousException()
        else:
            raise NoPackagesDefinedException()
        if not packageInfo:
            raise NoPackageSelectedException()
        root = args.rootdir;
        data = {'root':root,'patterns':args.patterns,'files':[]}
        path.walk(root, _collect_manifest_files, data)
        if args.verbose:
            for file in data['files']:
                print file
        packageInfo.set_manifest_files(args.platform, data['files'])
        config.save()


class PackageSelectionAmbiguousException(Exception):
	pass


class NoPackageSelectedException(Exception):
	pass


class NoPackagesDefinedException(Exception):
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
