#!/usr/bin/python
# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
# $/LicenseInfo$

"""
Defines a system executable object which can be linked to cascade parameters.

Author : Alan Linden
Date   : 2010-09-29
"""

import os
import subprocess
import re

import common
import logging

logger = logging.getLogger('autobuild.executable')

class ExecutableError(common.AutobuildError):
    pass


class Executable(common.Serialized):
    """
    An executable object which invokes a provided command as subprocess.
    
    Attributes:
        command - The command to invoke.
        arguments - The arguments to pass to the command being invoked.
        options - The options to pass to the command being invoked.
        filters - Regexes to filter command output.
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
    
    def __init__(self, command=None, options=[], arguments=None, filters=None, parent=None):
        self.command = command
        self.options = options
        self.arguments = arguments
        self.parent = parent
        self.filters = filters
    
    def __call__(self, options=[], environment=os.environ):
        # let the passed environment help us find self.command
        commandlist = self._get_all_arguments(options)
        prog = commandlist[0]
        # If prog is already absolute, leave it alone.
        if not os.path.dirname(prog):
            # prog is relative
            # Looking for PATH is a bit tricky: the capitalization of the name
            # might vary by platform. While we believe os.environ is a
            # case-insensitive dict, we can't be sure that the passed
            # 'environment' is necessarily such a dict.
            pathkey = [k for k in environment.iterkeys() if k.upper() == "PATH"]
            # If we can't find any such key, don't blow up, just don't replace
            # prog.
            if pathkey:
                # Remember pathkey is a list of matching keys -- pathkey[0]
                # extracts the actual key. Boldly use environment[] because we
                # already know pathkey[0] exists in environment!
                path = environment[pathkey[0]].split(os.pathsep)
                # Search for 'prog' on THAT path.
                prog = common.find_executable(prog, path=path)
                # find_executable() returns None if not found
                if prog:
                    commandlist[0] = prog
        
        filters = self.get_filters()
        if not filters:
            # no filtering, dump child stdout directly to our own stdout
            logger.debug("subprocess %s" % ' '.join(commandlist))
            return subprocess.call(commandlist, env=environment)
        else:
            # have to filter, so run stdout through a pipe
            logger.debug("running subprocess %s filtered %s" % (' '.join(commandlist), filters))
            process = subprocess.Popen(commandlist, env=environment,
                                       stdout=subprocess.PIPE)
            filters_re = [re.compile(filter, re.MULTILINE) for filter in filters]
            for line in process.stdout:
                if any(regex.search(line) for regex in filters_re):
                    continue
                line = line.replace("\r\n", "\n")
                line = line.replace("\r", "\n")
                print line,  # Trailing , prevents an extra newline
            return process.wait()
   
    def __str__(self, options=[]):
        try:
            return ' '.join(self._get_all_arguments(options))
        except:
            return 'INVALID EXECUTABLE!'
    
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
            return None
    
    def get_filters(self):
        """
        Returns the filters on command output.
        """
        if self.filters is not None:
            return self.filters
        elif self.parent is not None:
            return self.parent.get_filters()
        else:
            return None
    
    def _get_all_arguments(self, options):
        actual_command = self.get_command()
        if actual_command is None:
            raise ExecutableError('no command specified')
        all_arguments = [actual_command]
        all_arguments.extend(self.get_options())
        all_arguments.extend(options)
        all_arguments.extend(self.get_arguments())
        return all_arguments        
