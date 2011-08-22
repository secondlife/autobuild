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

# simple test runner, superseded by nose, but might be handy for something
# built to try out argparse while working with the existing tests

import sys
import os
import common
import argparse
import unittest

sys.path.append(os.getcwd() + '/../')       # for autobuild scripts
sys.path.append(os.getcwd() + '/tests/')    # for test suites

class text_colours:
    warning = '\033[91m'
    title = '\033[92m'
    end = '\033[0m'

# global lists of files, all testable files, those to skip and alternatively those to run
main_test_list=[]
main_test_skip_list=[]
main_test_run_list=[]

# find all testable code in this directory, and warn about non tested files
def find_all_tests():
    all_files=os.listdir('.')
    for file_name in all_files:
        if(file_name.endswith('.py') and
            file_name != '__init__.py'):
            test_file_name = './tests/test_' + file_name 
            if(os.path.isfile(test_file_name)):
                module_name=file_name[:-3] 
                main_test_list.append(module_name)
            else:
                print (text_colours.warning + "warning: file %r does not appear to have test coverage" +
                        text_colours.end) % file_name

# run the tests which have been chosen by the user
def run_list_of_tests(list, list_to_skip):
    for test_name in list:
        if(test_name in list_to_skip):
            print (text_colours.title + 'Skipping %r' + text_colours.end) % test_name
        else:
            test_file = 'test_' + test_name
            print (text_colours.title + 'Running tests for %r in module %r...' + text_colours.end) % (test_name, test_file)
            test_suite = __import__(test_file, globals(), locals(), [], -1);
            suite = unittest.TestLoader().loadTestsFromModule(test_suite)
            unittest.TextTestRunner(verbosity=2).run(suite)

# stub called by argparse for the --RunList/--RunTests options
class add_run_tests(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        for test_name in values:
            if(test_name not in main_test_run_list):
                main_test_run_list.append(test_name)

# stub called by argparse for the --SkipList/--SkipTests options
class add_skip_tests(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        for test_name in values:
            if(test_name not in main_test_skip_list):
                main_test_skip_list.append(test_name)

# this is if you want to call run all tests from an add_argument()
# not used atm
class run_all_tests(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        find_all_tests()




if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description='Run unit autobuild unit tests', prog='runtest')

    parser.add_argument('-v', '--version', action='version', version='%(prog)s 1.0')

#-------------------------
# simple version:

    parser.add_argument(
        '--RunTests', action=add_run_tests, nargs='+',
        help='Run a list of unit tests '
             '(default: run them all)')

    parser.add_argument(
        '--SkipTests', action=add_skip_tests, nargs='+',
        help='Skip a list of unit tests '
             '(default: run them all)')

    find_all_tests()


#-------------------------
# subcommand version:

#   subparsers = parser.add_subparsers(title='Sub Commands',
#                   description='Valid Sub Commands',
#                   help='Sub Command help')
#
#   parser_testlists = subparsers.add_parser('RunTests',
#       help='Provide lists of source files to test or skip');
#   
#   parser_testlists.add_argument(
#        '--SkipList', action=add_run_tests, nargs='+',
#        help='Run a list of unit tests'
#             '(default: run them all)')
#
#   parser_testlists.add_argument(
#        '--RunList', action=add_skip_tests, nargs='+',
#        help='Skip a list of unit tests'
#             '(default: run them all)')
#
#   parser_testlists.set_defaults(func=find_all_tests)

#-------------------------

    args = parser.parse_args()

    # subcommand version leaves this as the default argument
#   if(args.func):
#       args.func();

    if(len(main_test_run_list) != 0):
        run_list_of_tests(main_test_run_list, main_test_skip_list)
    else:
        if(len(main_test_list) != 0):
            run_list_of_tests(main_test_list, main_test_skip_list)
