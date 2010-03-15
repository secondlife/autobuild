#!/usr/bin/env python

import sys
import os
import subprocess

def main(options, args):
    subprocess.call([os.path.join(os.getcwd(), options.build_command)])

if __name__ == "__main__":
    import autobuild_main
    options, args = autobuild_main.parse_args(sys.argv[1:])
    sys.exit( main( options, args ) )

