# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$

"""
High-level option parsing functionality for autobuild.

This module parses the autobuild command line and runs the appropriate
sub-command.
"""

import sys
import os
import optparse

class OptionParser(optparse.OptionParser):
    def __init__(self):
        default_platform = {
            'linux2':'linux',
            'win32':'windows',
            'cygwin':'windows',
        }.get(sys.platform, sys.platform)

        #package usage="\n    %prog -t expat GL\n    %prog -u ../tarfile_tmp/expat-1.2.5-darwin-20080810.tar.bz2\n    %prog -i ./tmp/zlib*.tar.bz2 ../glh_lin*.bz2", 
        #package description="""Create tar archives from library files, and upload as appropriate.  Tarfiles will be formed from paths as specified in the manifest in autobuild.xml, or alternately 'configdir', if supplied as a command-line argument.""")

        optparse.OptionParser.__init__(self, usage="\n\t%prog [options] command [commandopts]\n\twhere command is one of 'install' 'configure' 'build' 'package' or 'upload'")
        self.add_option('--package-info', default='autobuild.xml',
            help="file containing package info database (for now this is llsd+xml, but it will probably become sqlite)")
        self.add_option('--verbose', '-v', action='store_true', default=False)
        self.add_option('--install-dir', default='build-linux-i686-relwithdebinfo/packages',
            help="directory to install packages into")
        self.add_option('--platform', type='string', default=default_platform,
            help="Specify platform to use: linux, darwin, or windows.  Left unspecified, the current platform will be used (formerly all three platforms were used).")


        ##########
        # BEGIN packaging options
        ##########
        self.add_option('--version', type='string', default="", dest='version',
            help='Overrides the version number for the specified library(ies).  If unspecified, the version number in "versions.txt" (in configdir) will be used, if present.  Can be left blank.')
        #self.add_option('-i', '--install', action='store_true', default=False, dest='install',
        #    help='Update autobuild.xml with the data for the specified tarfile(s). List paths to tarfiles to update (supports glob expressions).  Use --s3 option if appropriate (read about --s3 option).')

        self.add_option('--configdir', type='string', default=os.getcwd(), dest='configdir',
            help='Specify the config directory to use.  Defaults to current working directory.  If configdir specified, tarfiles will be assembled relative to root of tree containing configdir.')
        self.add_option('--tarfiledir', type='string', default="", dest='tarfiledir',
            help='Specify the directory in which to store new tarfiles.  Defaults to "tarfile_tmp".')
        self.add_option('--dry-run', action='store_true', default=False, dest='dry_run',
            help='Show what would be done, but don\'t actually do anything.')
        ##########
        # END packaging options
        ##########

        self.add_option('--build-command', type='string', default='build.sh', dest='build_command',
            help="command to execute for building a package (defaults to 'build.sh' or whatever's specified in autobuild.xml")

def parse_args(args):
    parser = OptionParser()
    return parser.parse_args(args)

sub_commands = dict(package=('package','main'),
                    upload=('upload','main'),
                    build=('build', 'main'))

def main(args):
    parser = OptionParser()
    options,extra_args = parser.parse_args(args)
    if options.verbose:
        print "options:'%r', args:%r" % (options.__dict__, args)

    if not extra_args:
        parser.print_usage()
        print >>sys.stderr, "run '%s --help' for more details" % sys.argv[0]
        return 1

    if extra_args[0] == 'install':
        import autobuild_tool_install
        return autobuild_tool_install.main([a for a in args if a != 'install'])

    if extra_args[0] == 'configure':
        import configure
        return configure.main(args[1:])

    try:
        # see http://docs.python.org/library/functions.html#__import__
        # and http://docs.python.org/library/functions.html#getattr
        command_name = extra_args[0]
        module_name, function_name = sub_commands[command_name]
        module = __import__("autobuild.%s" % module_name, fromlist=[module_name])
        sub_command = getattr(module, function_name)
        return sub_command(options, extra_args[1:])
    except KeyError, err:
        print >>sys.stderr, err
    except AttributeError, err:
        print >>sys.stderr, err
        print >>sys.stderr, dir(module)
        print >>sys.stderr, module

    parser.print_usage()
    print >>sys.stderr, "run '%s --help' for more details" % sys.argv[0]
    return 1

if __name__ == "__main__":
    sys.exit( main( sys.argv[1:] ) )

