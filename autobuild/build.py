# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$

"""
Autobuild helper command to build a project from the command line
"""

import os
import sys
import getopt
import common
import configure
from common import AutobuildError

class PlatformBuild(object):
    def __init__(self):
        pass

    def find_existing_directory(self, name, dirs):
        for dir in dirs:
            if os.path.exists(dir):
                return dir
        raise AutobuildError("Cannot find an installation of %s" % name)

    def find_file_by_ext(self, dir, ext):
        found = None
        ext = ext.lower()
        for file in os.listdir(dir):
            file_ext = os.path.splitext(file).lower()
            if file_ext == ext:
                if found:
                    raise AutobuildError("Multiple files with %s ext in %s. Use --project to specify." % ext, dir)
                found = file
        if not found:
            raise AutobuildError("Cannot find file with %s ext in %s. Use --project to specify." % ext, dir)
        return found

    def run(self, cmd):
        print cmd
        return os.system(cmd) >> 8

    def build(self, build_dir, build_type, target, project):
        raise AutobuildError("You cannot call PlatformBuild directly")
        

class WindowsBuild(PlatformBuild):

    vs_search = [
        "C:/Program Files/Microsoft Visual Studio 9.0/",
        "C:/Program Files/Microsoft Visual Studio 8.0/",
        ]

    def build(self, build_dir, build_type, target, project):
        if not target: target = 'INSTALL'
        if not project: project = self.find_file_by_ext(build_dir, '.sln')
        vs_dir = self.find_existing_directory("Visual Studio", vs_search)

        cmd = os.path.join(vs_dir, "Common7", "IDE", "devenv.com")
        cmd += ' ' + os.path.join(build_dir, project)
        cmd += ' /build "' + build_type + '"'
        cmd += ' /project "' + project + '"'
        sys.exit(self.run(cmd))

class LinuxBuild(PlatformBuild):
    def build(self, build_dir, build_type, target, project):
        if not target: target = 'install'

        if build_dir.endswith('relwithdebinfo') and build_type != 'RelWithDebInfo':
            build_dir = build_dir.replace('relwithdebinfo', build_type.lower())

        cmd = 'make -C "' + build_dir + '"'
        cmd += ' "' + target + '"'
        sys.exit(self.run(cmd))

class DarwinBuild(PlatformBuild):
    def build(self, build_dir, build_type, target, project):
        if not target: target = 'install'
        cmd = 'xcodebuild -project ' + os.path.join(build_dir, project)
        cmd += ' -target "' + target + '"'
        cmd += ' -configuration "' + build_type + '"'
        cmd += ' -sdk macosx10.5'
        cmd += " | grep -v '^    setenv '"
        sys.exit(self.run(cmd))

usage_msg = '''
Usage:   llbuild [options] [target]

Helper tool to build an autobuild project from the command line.

Options:
  -h | --help           print this help message
  -b | --builddir=DIR   the directory to perform the build in
  -t | --type=NAME      build type ("Debug", "Release", or "RelWithDebInfo")
  -p | --project=NAME   the name of the XCode project or VS solution file

  [target]              the name of the build target to build, e.g. 'install'
'''

def main(arguments):

    # setup default values for our options
    build_dir = configure.get_install_dir()
    target = None
    build_type = 'RelWithDebInfo'
    project = None
    show_help = False

    # parse the command line options
    try:
        opts, args = getopt.getopt(
            arguments,
            'hb:t:p:',
            ['help', 'builddir=', 'type=', 'project='])
    except getopt.GetoptError, err:
        print >> sys.stderr, 'Error:', err
        return 1

    for o, a in opts:
        if o == "-h" or o == "--help":
            show_help = True
        if o == "-b" or o == "--builddir":
            build_dir = a
        if o == "-t" or o == "--type":
            build_type = a
        if o == "-p" or o == "--project":
            project = a

    # display help usage if -h or more than one target
    if show_help or len(args) > 1:
        print >> sys.stderr, usage_msg.strip()
        return 1

    # support an option position argument as the target
    if args:
        target = args[0]

    # find the platform-specific build class
    build_platform = {
        'darwin': DarwinBuild,
        'linux2': LinuxBuild,
        'win32' : WindowsBuild,
        'cygwin' : WindowsBuild
        }

    if sys.platform not in build_platform.keys():
        raise AutobuildError("Unsupport build platform %s" % sys.platform)

    # and do the build for the current platform
    p = build_platform[sys.platform]()
    p.build(build_dir, build_type, target, project)


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except CommandError, err:
        print >> sys.stderr, 'Error:', err
        sys.exit(1)
