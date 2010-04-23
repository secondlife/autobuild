#!/usr/bin/env python

# example module for the new autobuild script
# registers itself via autobuild_tool.register

import sys
import os
import common
import argparse
import unittest

import autobuild_base

# Main tool functionality

# these two and the following two classes show how to use callbacks on your arguments
# and options
optional_value = 0
main_args = []

# I've used a really hacky global store for these, just as a demonstration
class run_test(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        global main_args
        # values in this case is a list of the positional arguments supplied to --Test
        main_args = values;
        pass

class run_test_option(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        global optional_value
        # grab the first argument supplied to --options
        optional_value = values[0]
        pass

# this is the main class, it overrides some of its base class to enable plugging into
# autobuild.py, the __main__ catch at the end means this tool will also run standalone
# using the standalone code from its base class
class autobuild_tool(autobuild_base.autobuild_base):

    # name is the tool name - ie 'example' (for use from autobuild.py)
    # when run from autobuild 'description' forms the help for this subcommand
    # when run standalone it forms the tool desciption
    def get_details(self):
        return dict(name=self.name_from_file(__file__),
                    description='Example Tool for Autobuild')
    
    # called by autobuild to add help and options to the autobuild parser, and by
    # standalone code to set up argparse
    def register(self, parser):
        parser.add_argument('-v', '--version', action='version', version='test tool module 1.0')

        # nargs='*' here means an optional list of positional arguments
        parser.add_argument(
            'positional_arg_list', nargs='*',
            help='takes a list of one or more arguments and leaves them in args["positional_arg_list"]')

        # nargs='+' here means an one or more arguments, but at least one is required
        # action=run_test makes run_test get called when this option is parsed with its own
        # arguments list
        parser.add_argument(
            '--Test', action=run_test, nargs='+',
            help='Test Tool Internal Help')

        # here no action is specified so the list of positional arguments is just added to
        # a list called TestListArg in the args passed to run()
        parser.add_argument(
            '--TestArgList', nargs='+',
            help='Test Tool Internal Help')

        # adding the leading dashes (or single dash) makes an argument optional
        # this one also uses a callback to act on it's setting
        parser.add_argument(
            '--option', action=run_test_option,
            help='Test Tool test optional')

        # this option automatically stores False if not present, True if it's there
        parser.add_argument(
            '-o', action='store_true',
            help='Test Tool test optional')

    # this is your main callback once the args have been parsed, you can parse the args it gets
    # directly or in callbacks provided earlier. the cheapy locals dumper at the end of this
    # example is a good way to work out whats going on, the "('args', Namespace(..." output is
    # the complete contents of the args namespace.
    def run(self, args):
        # accessing the globals set by callbacks:
        global optional_value
        global main_args
        argstring = ('%r' % optional_value)+''.join(main_args)
        print 'the answer is:' + argstring
        # accessing args directly:
        print 'the -o option is set to ' + str(args.o)
        # and finally dump out the whole of our local namespace so you can see whats in args
        # and how its layed out
        print 'and the returned args are:'
        for arg in locals().items():
            print arg

# provide this line to make the tool work standalone too (which all tools should)
if __name__ == "__main__":
    sys.exit( autobuild_tool().main( sys.argv[1:] ) )
