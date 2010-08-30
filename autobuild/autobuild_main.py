#!/usr/bin/env python

import sys
import os
import common
import argparse

class run_help(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        parser.parent.search_for_and_import_tools(parser.parent.tools_list)
        parser.parent.register_tools(parser.parent.tools_list)
        print parser.format_help()
        parser.exit(0)


class Autobuild(object):
    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description='Autobuild', prog='autobuild', add_help=False)
        
        self.parser.add_argument('-v', '--version', action='version', version='%(prog)s 1.0')

        self.subparsers = self.parser.add_subparsers(title='Sub Commands',
            description='Valid Sub Commands',
            help='Sub Command help')

    def listdir(self, dir):
        files = os.listdir(dir)
        if 'autobuild_tool_test.py' in files:
            del files[files.index('autobuild_tool_test.py')]
        return files

    def register_tool(self, tool):
        newtool = tool.autobuild_tool()
        details = newtool.get_details()
        self.new_tool_subparser = self.subparsers.add_parser(details['name'], help=details['description']);
        newtool.register(self.new_tool_subparser)
        return newtool

    def register_tools(self, tools_list):
        for tool in tools_list:
            self.register_tool(tool)
    
    def search_for_and_import_tools(self, tools_list):
        autobuild_package_dir = os.path.dirname(__file__)
        all_files=self.listdir(autobuild_package_dir)
        for file_name in all_files:
            if(file_name.endswith('.py') and
                file_name != '__init__.py' and
                file_name.startswith('autobuild_tool_')):
                module_name=file_name[:-3]
                possible_tool_module = __import__(module_name, globals(), locals(), []);
                if(getattr(possible_tool_module, 'autobuild_tool', None)):
                    tools_list.append(possible_tool_module)

    def try_to_import_tool(self, tool, tools_list):
        autobuild_package_dir = os.path.dirname(__file__)
        tool_module_name = 'autobuild_tool_' + tool
        tool_file_name = tool_module_name + '.py'
        full_tool_path = os.path.join(autobuild_package_dir, tool_file_name)
        if os.path.exists(full_tool_path):
            possible_tool_module = __import__(tool_module_name, globals(), locals(), []);
            if(getattr(possible_tool_module, 'autobuild_tool', None)):
                tools_list.append(possible_tool_module)
                instance = self.register_tool(possible_tool_module)
                return instance
        return -1


    def main(self, args_in):
    	os.environ['AUTOBUILD_PROCESS_DIR'] = os.getcwd()
    
        self.tools_list = []
        
        self.parser.parent = self
        self.parser.add_argument('--help',
        help='Find all valid Autobuild Tools and show help', action=run_help,
        nargs='?', default=argparse.SUPPRESS)

        argdefs = (
            (('--dry-run',),
             dict(help='Run tool in dry run mode if available', action='store_true')),
             (('-C','--directory'),dict(
             	dest='autobuild_root_dir', nargs='?', default=os.environ.get('AUTOBUILD_ROOT_DIR'),
             	help='Sets the autobuild root directory.'))
            )

        for args, kwds in argdefs:
            self.parser.add_argument(*args, **kwds)
        
        tool_to_run = -1;

        for arg in args_in:
            if arg[0] != '-':
                tool_to_run = self.try_to_import_tool(arg, self.tools_list)
                if tool_to_run != -1:
                    # Define all the global arguments as also being legal
                    # for the subcommand, e.g. support both
                    # autobuild --dry-run upload args... and
                    # autobuild upload --dry-run args...
                    for args, kwds in argdefs:
                        self.new_tool_subparser.add_argument(*args, **kwds)
                break

        args = self.parser.parse_args(args_in)
        
        if not args.autobuild_root_dir:
            args.autobuild_root_dir = os.getcwd()
       	os.environ['AUTOBUILD_ROOT_DIR'] = args.autobuild_root_dir
 
        if tool_to_run != -1:
            tool_to_run.run(args)

        return 0

if __name__ == "__main__":
    sys.exit( Autobuild().main( sys.argv[1:] ) )



