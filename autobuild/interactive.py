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
    

