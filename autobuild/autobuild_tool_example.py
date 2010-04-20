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
		
class autobuild_tool(autobuild_base.autobuild_base):

	def get_details(self):
		return dict(name='example', description='Example Tool for Autobuild')
	
	def register(self, parser):
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
		global optional_value
		global main_args
		argstring = ('%r' % optional_value)+''.join(main_args)
		print 'the answer is:' + argstring

if __name__ == "__main__":
	sys.exit( autobuild_tool().main( sys.argv[1:] ) )
	
	