#!/usr/bin/env python
# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$


import argparse
import os
import sys

import autobuild_base
from autobuild_tool_manifest import construct_manifest
import common
import configfile


class autobuild_tool(autobuild_base.autobuild_base):
    def get_details(self):
        return dict(name='bootstrap',
            description="Run an interactive session to build an Autobuild configuration file")
     
    def register(self, parser):
        parser.add_argument('file', default=configfile.BUILD_CONFIG_FILE, nargs='?',
            help='A configuration file to bootstrap')

    def run(self, args):
        self.args = args
        self.activity = None
        self.set_activity(_LoadingConfig(self))
    
    def set_activity(self, activity):
        if self.activity is not None: 
            self.activity.exit()
        self.activity = activity
        self.activity.enter()
    
    def ask_to_save(self):
        print "Would you like to save your updates?"
        if _input_yes_or_no():
            result = self.config.save(self.args.file)
            if not result:
                print >> sys.stdderr, "unable to save file"


class _LoadingConfig(object):
    def __init__(self, machine):
        self.machine = machine
    
    def enter(self):
        config = configfile.ConfigFile()
        self.machine.config = config
        try:
            config.load(machine.args.file)
        except:
            pass
        name = None
        while name is None or name == '':
            print "Enter package name."
            name = _input_text("name")
        if config.package(name) is not None:
            print "The package '%s' is already defined; overwrite?" % name
            if _input_yes_or_no() is False:
                self.machine.set_activity(_Ending(self.machine))
                return
        packageInfo = configfile.PackageInfo() 
        config.set_package(name, packageInfo)
        self.machine.packageInfo = packageInfo
        self.machine.set_activity(_SelectingPlatform(self.machine))
        
    def exit(self):
        pass


class _SelectingPlatform(object):
    def __init__(self, machine):
        self.machine = machine

    def enter(self):
        print "Would you like to bootstrap a platform?"
        if _input_yes_or_no() is False:
            self.machine.set_activity(_Ending(self.machine))
            return
        print "Choose a platform:"
        self.machine.platform = _input_choice(common.PLATFORMS, common.get_current_platform())
        self.machine.set_activity(_SettingConfigurationCommand(self.machine))
        
    def exit(self):
        pass


class _SettingConfigurationCommand(object):
    def __init__(self, machine):
        self.machine = machine
        self.modified = False
    
    def enter(self):
        print "Configure the configuration command?"
        if _input_yes_or_no():
            self._configure_configuration()
        self.machine.set_activity(_SettingBuildCommand(self.machine))

    def exit(self):
        if self.modified:
            self.machine.ask_to_save()
    
    def _configure_configuration(self):
        print "Choose configuration type:"
        configurationType = _input_choice(self._configurationTypes)
        while True:
            if configurationType == "manual...":
                self._manual_configuration()
            print "The configuration command is: ", self.machine.packageInfo.configure_command(
                self.machine.platform)
            if _input_choice(("accept", "start over"), "accept") == "accept":
                break
        self.modified = True
        
    def _manual_configuration(self):
        print "Enter command."
        self.machine.packageInfo.set_configure_command(
            self.machine.platform, _input_text("command"))
    
    _configurationTypes = ("manual...",)


class _SettingBuildCommand(object):
    def __init__(self, machine):
        self.machine = machine
        self.modified = False
    
    def enter(self):
        print "Configure the build command?"
        if _input_yes_or_no():
            self._configure_build()
        self.machine.set_activity(_Packaging(self.machine))

    def exit(self):
        if self.modified:
            self.machine.ask_to_save()

    def _configure_build(self):
        print "Choose build type:"
        buildType = _input_choice(self._buildTypes)
        while True:
            if buildType == "manual...":
                self._manual_build()
            print "The build command is: ", self.machine.packageInfo.build_command(
                self.machine.platform)
            if _input_choice(("accept", "start over"), "accept") == "accept":
                break
        print "Enter build directory."
        self.machine.packageInfo.builddir = _input_text("build dir")
        self.modified = True
        
    def _manual_build(self):
        print "Enter command."
        self.machine.packageInfo.set_build_command(
            self.machine.platform, _input_text("command"))
    
    _buildTypes = ("manual...",)


class _Packaging(object):
    def __init__(self, machine):
        self.machine = machine
        self.modified = False
    
    def enter(self):
        print "Add packaging information?"
        if _input_yes_or_no():
            self._configure_package()
        self.machine.set_activity(_Publishing(self.machine))    

    def exit(self):
        if self.modified:
            self.machine.ask_to_save()

    def _configure_package(self):
        print "Enter the directory into which the source should be extracted."
        self.machine.packageInfo.sourcedir = _input_text("dir")
        self._choose_license()
        self._build_manifest()
        self.modified = True
        
    def _choose_license(self):
        print "Choose license:"
        license = _input_choice(self._licenses)
        if license == "other...":
            print "Enter license."
            license = _input_text("license")
        print "Enter license file."
        machine.packageInfo.licensefile = _input_text("file")
        self.machine.packageInfo.license = license

    def _build_manifest(self):
        patterns = []
        while True:
            print "Enter files (wildcards *, ?. and [...] supported) to add to the manifest or an",\
                "empty line to finish."
            while True:
                pattern = _input_text("file")
                if pattern == "":
                    break
                patterns.append(pattern)
            print "Add more files?"
            choice = _input_choice(("done", "start over", "add more"), "done")
            if choice == "done":
                break
            elif choice == "start over":
                patterns = []
            else:
                pass
        construct_manifest(self.machine.packageInfo, patterns, self.machine.platform)
    
    _licenses = ('gpl','mit', 'cluck like a chicken', 'other...')


class _Publishing(object):
    def __init__(self, machine):
        self.machine = machine
        self.modified = False
    
    def enter(self):
        print "Add publishing information?"
        if _input_yes_or_no():
            self._configure_repository()
        self.machine.set_activity(_SelectingPlatform(self.machine))    

    def exit(self):
        if self.modified:
            self.machine.ask_to_save()

    def _configure_repository(self):
        print "Choose repository type:"
        self.machine.packageInfo.sourcetype = _input_choice(self._repositoryTypes)
        print "Enter source URL."
        self.machine.packageInfo.source = _input_text("URL")
        self.modified = True

    _repositoryTypes = ("archive", "svn", "hg", "pypi", "perforce", "cvs", "git", "other...")


class _Ending(object):
    def __init__(self, machine):
        self.machine = machine

    def enter(self):
        self.machine.ask_to_save()
    
    def exit(self):
        pass


def _input_text(tag=""):
    return raw_input("[%s]> " % tag)


def _input_yes_or_no():
    while True:
        input = raw_input("[y/n]> ")
        input.lower()
        if input == 'y' or input == 'yes':
            return True
        if input == 'n' or input == 'no':
            return False


def _input_bounded_integer(low, hi, default=None):
    while True:
        input = raw_input("[%u-%u]> " % (low, hi))
        if input == '' and default is not None:
            return default
        else:
            try:
                result = int(input)
                if low <= result <= hi:
                    return result
            except ValueError:
                pass


def _input_choice(choices, default=None):
    defaultIndex = None
    for i in xrange(0, len(choices)):
        choice = choices[i]
        if choice == default:
            tag = '*'
            defaultIndex = i
        else:
            tag = ' '
        print "%c% 2u) %s" % (tag, i + 1, choice)
    if defaultIndex is not None:
        defaultIndex += 1
    selection = _input_bounded_integer(1, len(choices), defaultIndex)
    return choices[selection - 1]
    

if __name__ == "__main__":
    sys.exit( autobuild_tool().main( sys.argv[1:] ) )
