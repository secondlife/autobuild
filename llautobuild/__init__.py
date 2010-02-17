
import optparse

class __OptionParser(optparse.OptionParser):
    def __init__(self):
        optparse.OptionParser.__init__(self)
        self.add_option('--package-info', default='install.xml',
            help="file containing package info database (for now this is llsd+xml, but it will probably become sqlite)")
        self.add_option('--verbose', '-v', action='store_true', default=False)
 
def main(args):
    parser = __OptionParser()
    options,args = parser.parse_args(args)
    if options.verbose:
        print "options:'%r', args:%r" % (options.__dict__, args)
    return 0

