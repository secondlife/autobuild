#!/usr/bin/env python

import sys
import os
import common
import argparse
import logging

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
        if 'AutobuildTool_test.py' in files:
            del files[files.index('AutobuildTool_test.py')]
        return files

    def register_tool(self, tool):
        newtool = tool.AutobuildTool()
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
                if(getattr(possible_tool_module, 'AutobuildTool', None)):
                    tools_list.append(possible_tool_module)

    def try_to_import_tool(self, tool, tools_list):
        autobuild_package_dir = os.path.dirname(__file__)
        tool_module_name = 'autobuild_tool_' + tool
        tool_file_name = tool_module_name + '.py'
        full_tool_path = os.path.join(autobuild_package_dir, tool_file_name)
        if os.path.exists(full_tool_path):
            possible_tool_module = __import__(tool_module_name, globals(), locals(), []);
            if(getattr(possible_tool_module, 'AutobuildTool', None)):
                tools_list.append(possible_tool_module)
                instance = self.register_tool(possible_tool_module)
                return instance
        return -1


    def main(self, args_in):
    
        self.tools_list = []
        
        self.parser.parent = self
        self.parser.add_argument('--help',
            help='find all valid Autobuild Tools and show help', action=run_help,
            nargs='?', default=argparse.SUPPRESS)
        
        argdefs = (
            (('--dry-run',),
                dict(help='run tool in dry run mode if available', action='store_true')),
             (('--quiet',),
                dict(help='minimal output', action='store_const',
                    const=logging.ERROR, dest='logging_level', default=logging.WARNING)),
             (('--verbose',),
                dict(help='verbose output', action='store_const', const=logging.INFO, dest='logging_level')),
             (('--debug',),
                dict(help='debug output', action='store_const', const=logging.DEBUG, dest='logging_level')),
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
                
        logger = logging.getLogger('autobuild')
        logger.setLevel(args.logging_level)
        logger.addHandler(logging.StreamHandler())
 
        if tool_to_run != -1:
            tool_to_run.run(args)

        return 0

if __name__ == "__main__":
    sys.exit( Autobuild().main( sys.argv[1:] ) )



