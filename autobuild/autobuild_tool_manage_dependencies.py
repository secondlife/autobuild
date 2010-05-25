#!/usr/bin/env python
        
# manage a packages.xml's dependencies, add them, remove them, find and print them

import sys
import os
import common
import argparse
import unittest
import configfile

import autobuild_base

class autobuild_tool(autobuild_base.autobuild_base):

    def get_details(self):
        return dict(name=self.name_from_file(__file__),
                    description='Manage dependencies in a Package.xml')
    
    def register(self, parser):
        parser.add_argument('-v', '--version', action='version', version='dependencies tool module 1.0')

        parser.add_argument('--config-file', help='Path of the package config file you wish to edit', default='packages.xml')
        parser.add_argument('--create', action='store_true', help='Create package config file if necessary')
        
        parser.add_argument('--add', nargs='+', help='Packages to add in the form:\n name,platform,url,md5,description,copywrite,license,licencefile\n leave blank to ignore, this will update existing entries leaving blanks unchanged.')
        parser.add_argument('--remove', nargs='+', help='Packages to remove')
        parser.add_argument('--list', action='store_true', help='Print Package list')

        parser.add_argument('--verbose', action='store_true', help='Print out lots of lovely information')
        pass

    def run(self, args):

        c = configfile.ConfigFile()
        if getattr(args, 'config_file', None) == None:
            print "No package config file Specified"
            return
            
        ret = c.load(args.config_file)
        if ret != False or args.create:
            print "Package loaded"
            print
            
            if args.list:
                print "Listing Packages in %s" % args.config_file
                print "No. of packages =", c.package_count
                for name in c.package_names:
                    package = c.package(name)
                    print "Package '%s'" % name
                print
            
            add = getattr(args, 'add', None)
            remove = getattr(args, 'remove', None)

            if add == None and remove == None:
                print "Nothing to do..."
                return
            
            if add != None:
                for addition in add:
                    splitup = addition.split(',')
                    if len(splitup) != 8:
                        print "I couldn't work out %s check help, it should be 'name,platform,url,md5,description,copywrite,license,licencefile'" % addition
                    else:
                        name = splitup[0]
                        packageInfo = c.package(name)
                        if packageInfo != None:
                            platform = splitup[1]
                            if splitup[2] != '':
                                packageInfo.set_archives_url(platform,splitup[2])
                            if splitup[3] != '':
                                packageInfo.set_archives_md5(platform,splitup[3])
                            if splitup[4] != '':
                                packageInfo.description = splitup[4]
                            if splitup[5] != '':
                                packageInfo.copyright = splitup[5]
                            if splitup[6] != '':
                                packageInfo.license = splitup[6]
                            if splitup[7] != '':
                                packageInfo.licensefile = splitup[7]
                            print 'Updating', name
                        else:
                            packageInfo = configfile.PackageInfo()
                            platform = splitup[1]
                            packageInfo.name = splitup[0]
                            packageInfo.set_archives_url(platform,splitup[2])
                            packageInfo.set_archives_md5(platform,splitup[3])
                            packageInfo.description = splitup[4]
                            packageInfo.copyright = splitup[5]
                            packageInfo.license = splitup[6]
                            packageInfo.licensefile = splitup[7]
                            if packageInfo.licensefile == '':
                                packageInfo.licensefile = 'LICENSES/%s.txt' % name
                            print 'Adding', name
                            
                        c.set_package(name, packageInfo)
            
            if remove != None:
                for removal in remove:
                    packageInfo = c.package(removal)
                    if packageInfo == None:
                        print "Package %s not found in %s" % (removal, args.config_file)
                    else:
                        print 'Removing', removal
                        del c.packages[removal]
                print
                
            if not args.dry_run:
                c.save()
            else:
                print 'Dry run, not saving'

            if args.verbose:
                for name in c.package_names:
                    package = c.package(name)
                    print "Package '%s'" % name
                    print "  Description: %s" % package.description
                    print "  Copyright: %s" % package.copyright
            print
        else:
            print "Package file not found"
        pass

if __name__ == "__main__":
    sys.exit( autobuild_tool().main( sys.argv[1:] ) )
