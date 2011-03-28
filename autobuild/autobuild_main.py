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

import sys
import os
import common
import argparse
import logging

## Environment variable name used for default log level verbosity
AUTOBUILD_LOGLEVEL = 'AUTOBUILD_LOGLEVEL'

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
        
        self.parser.add_argument('-V', '--version', action='version',
                                 version='%%(prog)s %s' % common.AUTOBUILD_VERSION_STRING)

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
        
    def get_default_loglevel_from_environment(self):
        """
        Returns a default log level based on the AUTOBUILD_LOGLEVEL environment variable

        This may be used directly by the user, but in combination with the
        set_recursive_loglevel method below also ensures 
        that any recursive invocation of autobuild inherits the same level as the
        parent, even if intervening commands do not pass it through.
        """
        try:
            environment_level = os.environ[AUTOBUILD_LOGLEVEL]
        except KeyError:
            environment_level = ''

        if environment_level == '--quiet' or environment_level == '-q' :
            return logging.ERROR
        elif environment_level == '':
            return logging.WARNING
        elif environment_level == '--verbose' or environment_level == '-v' :
            return logging.INFO
        elif environment_level == '--debug' or environment_level == '-d' :
            return logging.DEBUG
        else:
            raise AutobuildError("invalid %s value '%s'" % (AUTOBUILD_LOGLEVEL, environment_level))

    def set_recursive_loglevel(self, logger, level):
        """
        Sets the logger level, and also saves the equivalent option argument
        in the AUTOBUILD_LOGLEVEL environment variable so that any recursive
        invocation of autobuild uses the same level
        """
        logger.setLevel(level)

        if level == logging.ERROR:
            os.environ[AUTOBUILD_LOGLEVEL] = '--quiet'
        elif level == logging.WARNING:
            os.environ[AUTOBUILD_LOGLEVEL] = ''
        elif level == logging.INFO:
            os.environ[AUTOBUILD_LOGLEVEL] = '--verbose'
        elif level == logging.DEBUG:
            os.environ[AUTOBUILD_LOGLEVEL] = '--debug'
        else:
            raise common.AutobuildError("invalid effective log level %s" % logging.getLevelName(level))


    def main(self, args_in):
    
        logger = logging.getLogger('autobuild')
        logger.addHandler(logging.StreamHandler())
        default_loglevel = self.get_default_loglevel_from_environment() 

        self.tools_list = []
        
        self.parser.parent = self
        self.parser.add_argument('-h', '--help',
            help='find all valid Autobuild Tools and show help', action=run_help,
            nargs='?', default=argparse.SUPPRESS)
        
        argdefs = (
            (('-n', '--dry-run',),
                dict(help='run tool in dry run mode if available', action='store_true')),

            ## NOTE: if the mapping of verbosity controls (--{quiet,verbose,debug})
            ##       is changed here, it must be changed to match in set_recursive_loglevel
            ##       and get_default_loglevel_from_environment methods above.
             (('-q', '--quiet',),
                dict(help='minimal output', action='store_const',
                     const=logging.ERROR, dest='logging_level', default=default_loglevel)),
             (('-v', '--verbose',),
                dict(help='verbose output', action='store_const', const=logging.INFO, dest='logging_level')),
             (('-d', '--debug',),
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

        self.set_recursive_loglevel(logger, args.logging_level)

        if tool_to_run != -1:
            tool_to_run.run(args)

        return 0

def main():
    # find the path to the actual autobuild exectuable and ensure it's in PATH
    # so that build commands can find it and other scripts distributed with autobuild.
    script_path = os.path.dirname(common.get_autobuild_executable_path())

    logger = logging.getLogger('autobuild')
    try:
        os.environ['PATH'] = os.environ.get('PATH') + os.pathsep + script_path
        sys.exit( Autobuild().main(sys.argv[1:]) )
    except KeyboardInterrupt, e:
        sys.exit("Aborted...")
    except common.AutobuildError, e:
        if logger.getEffectiveLevel() <= logging.DEBUG:
            logger.exception(str(e))
        sys.exit("ERROR: %s\nFor more information: try re-running your command with --verbose or --debug" % e)

 
if __name__ == "__main__":
    main()

