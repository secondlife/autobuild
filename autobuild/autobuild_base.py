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

    def configurations_from_environment(self):
        cfgs=os.environ.get("AUTOBUILD_CONFIGURATION")
        if cfgs is None:
            return []
        else:
            return cfgs.split(",")

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
#   sys.exit( autobuild_base_standalone().main( sys.argv[1:] ) )
