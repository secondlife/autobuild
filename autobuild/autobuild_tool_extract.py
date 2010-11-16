# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$

'''
Extract files from an archive.

Very handy on e.g. Windows, where we probably don't have an unzip
executable.
'''

import autobuild_base

def extract_zip(opts, name):
    import zipfile

    z = zipfile.ZipFile(name, 'r')
    z.extractall(path=opts.install_dir)

def extract_tar(opts, name):
    import tarfile

    lname = name.lower()
    if lname.endswith('gz'):
        t = tarfile.TarFile.gzopen(name, 'r')
    elif lname.endswith('bz2'):
        t = tarfile.TarFile.bz2open(name, 'r')
    else:
        t = tarfile.TarFile.open(name, 'r')

    for i in t:
        t.extract(i, opts.install_dir or '')
    
def extract(opts, name):
    import re, sys

    lname = name.lower()
    if lname.endswith('.zip'):
        extract_zip(opts, name)
    elif re.match(r'.*\.(tar.gz|tgz|tar.bz2|tbz2|tar)$', lname):
        extract_tar(opts, name)
    else:
        print >> sys.stderr, 'Do not know how to extract %r' % name
        sys.exit(1)

def add_arguments(parser):
    parser.add_argument(
        'archive',
        nargs='*',
        help='List of archives to extract.')
    parser.add_argument(
        '--install-dir',
        default=None,
        dest='install_dir',
        help='Where to unpack the installed files.')

class AutobuildTool(autobuild_base.AutobuildBase):
    def get_details(self):
        return dict(name=self.name_from_file(__file__),
                    description='Extract files from an archive.')

    def register(self, parser):
        add_arguments(parser)

    def run(self, args):
        for a in args.archive:
            extract(args, a)

if __name__ == '__main__':
    sys.exit("Please invoke this script using 'autobuild %s'" %
             AutobuildTool().get_details()["name"])
