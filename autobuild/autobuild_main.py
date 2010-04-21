#!/usr/bin/env python

import sys
import os
import common
import argparse

class Autobuild():
    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description='Autobuild', prog='Autobuild')
        
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
        new_parser = self.subparsers.add_parser(details['name'], help=details['description']);
        newtool.register(new_parser)
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
                possible_tool_module = __import__(module_name, globals(), locals(), [], -1);
                if(getattr(possible_tool_module, 'autobuild_tool', None)):
                    tools_list.append(possible_tool_module)

    def try_to_import_tool(self, tool, tools_list):
        autobuild_package_dir = os.path.dirname(__file__)
        tool_module_name = 'autobuild_tool_' + tool
        tool_file_name = tool_module_name + '.py'
        full_tool_path = os.path.join(autobuild_package_dir, tool_file_name)
        if os.path.exists(full_tool_path):
            possible_tool_module = __import__(tool_module_name, globals(), locals(), [], -1);
            if(getattr(possible_tool_module, 'autobuild_tool', None)):
                tools_list.append(possible_tool_module)
                instance = self.register_tool(possible_tool_module)
                return instance
        return -1


    def main(self, args_in):
    
        parser_find_tools_help = self.subparsers.add_parser('ToolsHelp',
        help='Find all valid Autobuild Tools and show help');
        
        parser_find_tools_help.set_defaults(tools_help_requested=True)

        tools_list = []
        
        tool_to_run = -1;

        for arg in args_in:
            if arg[0] != '-' and arg != 'ToolsHelp':
                tool_to_run = self.try_to_import_tool(arg, tools_list)
                break

        args = self.parser.parse_args(args_in)

        if tool_to_run == -1:
            if getattr(args,'tools_help_requested', False):
                self.search_for_and_import_tools(tools_list)
                self.register_tools(tools_list)
                self.parser.print_help()
        else:
            tool_to_run.run(args)

        return 0

if __name__ == "__main__":
    sys.exit( Autobuild().main( sys.argv[1:] ) )



