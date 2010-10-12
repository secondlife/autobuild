#!/usr/bin/env python

# test module for the new autobuild script
# registers itself via autobuild_tool.register

import sys
import os
import common
import argparse
import unittest

import autobuild_base

optional_value = 0
main_args = []

class run_test(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        global main_args
        main_args = values;
        pass

class run_test_option(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        global optional_value
        optional_value = values[0]
        pass
        
class AutobuildTool(autobuild_base.AutobuildBase):

    def get_details(self):
        return dict(name=self.name_from_file(__file__),
                    description='Test Tool for Autobuild')

    def register(self, parser):
        print "Autobuild Test Tool Says Hi-De-Hi"

        parser.add_argument('-v', '--version', action='version', version='test tool module 1.0')

        parser.add_argument(
            '--Test', action=run_test, nargs='+',
            help='Test Tool Internal Help')

        parser.add_argument(
            '--option', action=run_test_option,
            help='Test Tool test optional')

        parser.add_argument(
            '-o', action='store_true',
            help='Test Tool test optional')

    def run(self, args):
        if args.dry_run:
            print 'Dry run mode in operation!'
        
        global optional_value
        global main_args
        argstring = ('%r' % optional_value)+''.join(main_args)
        print 'the answer is:' + argstring

