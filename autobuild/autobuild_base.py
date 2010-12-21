# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$

# Base Class to give autobuild tool modules integration into autobuild
# and standalone functionality

import sys
import os
import common
from common import AutobuildError
import argparse
import unittest

# Main tool functionality

class AutobuildBase:

    def name_from_file(self, filename):
        """
        Since an autobuild tool's module filename must conform to a particular
        naming convention, and that name must embed the tool's invocation
        name, provide a method to extract the tool name from __file__.
        """
        basename = os.path.splitext(os.path.basename(filename))[0]
        pfx = "autobuild_tool_"
        if basename.startswith(pfx):
            basename = basename[len(pfx):]
        return basename

# Override these three functions to hook into autobuild.py

    def get_details(self):
        # name is the tool name - ie 'example' (for use from autobuild.py)
        # when run from autobuild 'description' forms the help for this subcommand
        # when run standalone it forms the tool desciption
        return dict(name='', description='')
    
    def register(self, parser):
        pass

    def run(self, args):
        pass

# Standalone functionality:

    # not __init__ as we have to overload functions it calls
    def __init__(self):
        details = self.get_details()
        self.parser = argparse.ArgumentParser(description=details['description'])
        self.register(self.parser)
        
        #need some way to get the global options building up in autobuild_main - maybe split them into another .py
        self.parser.add_argument('--dry-run', action='store_true', help='Dry run only')
    
    def main(self, args_in):
        if len(args_in) < 1:
            self.parser.print_usage()
        else:
            args = self.parser.parse_args(args_in)
            self.run(args)
        pass

#if __name__ == "__main__":
#	sys.exit( autobuild_base_standalone().main( sys.argv[1:] ) )
