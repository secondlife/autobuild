#!/usr/bin/env python

# Base Class to give autobuild tool modules integration into autobuild
# and standalone functionality

import sys
import os
import common
import argparse
import unittest

# Main tool functionality

class autobuild_base:

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
			
	def main(self, args_in):
		args = self.parser.parse_args(args_in)
		self.run(args)
		pass

#if __name__ == "__main__":
#	sys.exit( autobuild_base_standalone().main( sys.argv[1:] ) )
	
	