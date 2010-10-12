#!/usr/bin/env python
        
# load a config file and then save it out again
# this ensures the file is in the latest format
# and that entries are in the canonical order.

import sys
import os
import configfile

import autobuild_base


class AutobuildTool(autobuild_base.autobuild_base):

    def get_details(self):
        return dict(name=self.name_from_file(__file__),
                    description='Rewrite the autobuild.xml file')
    
    def register(self, parser):
        parser.add_argument('-v', '--version',
                            action='version',
                            version='config file rewrite tool module 1.0')
        parser.add_argument('--config-file',
                            default=configfile.AUTOBUILD_CONFIG_FILE,
                            dest='config_file',
                            help='Path of the package config file you wish to update')

    def run(self, args):

        c = configfile.ConfigFile()
        print args
        ret = c.load(args.config_file)
        if ret:
            c.save()

if __name__ == "__main__":
    sys.exit( AutobuildTool().main( sys.argv[1:] ) )
