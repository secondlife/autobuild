# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$

"""
Defines a system executable object which can be linked to cascade parameters.

Author : Alan Linden
Date   : 2010-09-29
"""

from common import AutobuildError
from common import Serialized
import os
import sys
import subprocess


class ExecutableError(AutobuildError):
    pass


class Executable(Serialized):
    """
    An executable object which invokes a provided command as subprocess.
    
    Attributes:
        command - The command to invoke.
        arguments - The arguments to pass to the command being invoked.
        options - The options to pass to the command being invoked.
        parent - An Executable instance from which to inherit values from.
        
    Instances of this object may be chained by using the parent attribute.  If either the command or
    arguments attribute of this object is set to None, the value of the parents attribute will be
    used.  Options are merged with parent options coming before this objects options in the full 
    options list.
    
    E.g.:
        myExecutable = Executable(command='gcc', options=['-ggdb'], arguments=['foo.c', 'bar.c'])
        result = myExecutable()
    """
    
    parent = None
    
    def __init__(self, command=None, options=[], arguments=None, parent=None):
        self.command = command
        self.options = options
        self.arguments = arguments
        self.parent = parent
    
    def __call__(self, options=[]):
        actual_command = self.get_command()
        if actual_command is None:
            raise ExecutableError('no command specified')
        all_arguments = [actual_command]
        all_arguments.extend(self.get_options())
        all_arguments.extend(options)
        all_arguments.extend(self.get_arguments())
        return subprocess.call(' '.join(all_arguments), shell=True)
    
    def get_arguments(self):
        """
        Returns the arguments which will be passed to the command on execution. 
        """
        if self.arguments is not None:
            return self.arguments
        elif self.parent is not None:
            return self.parent.get_arguments()
        else:
            return []    
    
    def get_options(self):
        """
        Returns all options which will be passed to the command on execution. 
        """
        if self.parent is not None:
            all_options = self.parent.get_options()
        else:
            all_options = []
        all_options.extend(self.options)
        return all_options
    
    def get_command(self):
        """
        Returns the command this object will envoke on execution.
        """
        if self.command is not None:
            return self.command
        elif self.parent is not None:
            return self.parent.get_command()
        else:
            None
            