#!/usr/bin/env python

import sys
import optparse

class OptionParser(optparse.OptionParser):
    def __init__(self):
        optparse.OptionParser.__init__(self, usage="\n\t%prog [options] command [commandopts]\n\twhere command is one of 'install' 'configure' 'build' or 'package'\n\n\trun '%prog --help' for more details")
        self.add_option('--package-info', default='autobuild.xml',
            help="file containing package info database (for now this is llsd+xml, but it will probably become sqlite)")
        self.add_option('--verbose', '-v', action='store_true', default=False)
        self.add_option('--install-dir', default='build-linux-i686-relwithdebinfo/packages',
            help="directory to install packages into")
 
def main(args):
    parser = OptionParser()
    options,extra_args = parser.parse_args(args)
    if options.verbose:
        print "options:'%r', args:%r" % (options.__dict__, args)

    if not extra_args:
        parser.print_usage()
        parser.print_help()
        return 1

    if extra_args[0] == 'install':
        import install
        return install.main([a for a in args if a != 'install'])

    if extra_args[0] == 'configure':
        import configure
        return configure.main(args[1:])

    if extra_args[0] == 'package':
        import package
        return package.main([a for a in args if a != 'package'])

    return 0

if __name__ == "__main__":
    sys.exit( main( sys.argv[1:] ) )

