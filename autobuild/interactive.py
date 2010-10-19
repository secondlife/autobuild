#!/usr/bin/env python
# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$

"""
Classes and methods to support use of interactive mode commands.

Inherit from the InteractiveCommand class for some basic defaults.
You may find that you prefer to overload the class methods, rather than extend using 'super'.

See: autobuild_tool_edit.py for usage examples 
"""

import sys
from StringIO import StringIO
import configfile

class InteractiveCommand(object):
    """
    Class describing characteristics of a particular command.

    Should contain:
        description  description for interactive mode
        help         additional help text for interactive mode
        run          method used to run this command. Must take fields as keyword args.
    """

    def __init__(self, config):
        """
        This default __init__ for an interactive command has the following characteristics:
        
        config      an instance of configfile.ConfigurationDescription()

        description prints out the current configuration for a user to examine prior to modification
        help        text displayed providing info about field entry

        """
        stream = StringIO()
        stream.write("Current settings:\n")
        configfile.pretty_print(config, stream)
        self.description = stream.getvalue()
        self.help = "Enter new or modified configuration values."
        self.config = config

    def run(self, **kwargs):
        """
        kwargs is a dict of keyword arguments
        """
        pass
    
    def interactive_mode(self):
        """
        Utility to run a command in interactive mode.

        Requires:
            self to be a class describing the feature to be configured interactively.
        """
        try:
            data = getattr(self, 'ARGUMENTS')
        except AttributeError:
            raise AutobuildError("Interactive mode not supported.")

        command = '%s' % self.__class__.__name__
        command = command.lower()
        if getattr(self, 'description', ''):
            print '\n%s' % self.description
        print "\nUpdate %s details:" % command
        if getattr(self, 'help', ''):
            print self.help

        input_values = {}
        for argument in self.ARGUMENTS:
            try:
                i = raw_input("    %s> " % argument)
                if i:
                    if i.lower() == 'none':
                        i = ''
                    input_values[argument] = i
            except EOFError:
                print ""
                exit = 'y'
                exit = raw_input("Do you really want to exit ([y]/n)? ")
                if exit == 'y':
                    sys.exit(0)

        print "You input:"
        print "%s" % input_values
        save = raw_input("Save to config? ")
        if save in ['y', 'Y', 'yes', 'Yes', 'YES']:
            self.run(**input_values)
    


