"""
Classes and methods to support use of interactive mode commands.

Inherit from the InteractiveCommand class for some basic defaults.
You may find that you prefer to overload the class methods, rather than extend using 'super'.

See: autobuild_tool_edit.py for usage examples
"""

import sys
from io import StringIO

from autobuild import configfile
from autobuild.common import AutobuildError


class InteractiveCommand(object):
    """
    Class describing characteristics of a particular command.

    Should contain:
        description  description for interactive mode
        help         additional help text for interactive mode
        run          method used to run this command. Must take fields as keyword args.
        delete       method used to delete a config file entry.
    """

    HELP = ''

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

    def interactive_mode(self, delete=False):
        """
        Utility to run a command in interactive mode.

        Requires:
            self to be a class describing the feature to be configured interactively.
        """
        try:
            getattr(self, 'ARGUMENTS')
        except AttributeError:
            raise AutobuildError("Interactive mode not supported.")

        command = '%s' % self.__class__.__name__
        command = command.lower()
        if getattr(self, 'description', ''):
            print('\n%s' % self.description)

        action = "Create or update"
        if delete:
            action = "Delete"
        print("\n%s %s details:" % (action, command))
        if getattr(self, 'help', ''):
            print(self.help)
        print("Any fields left blank will remain unchanged.")
        print("Any fields entered as 'none' will clear the existing value.")

        input_values = {}
        for argument in self.ARGUMENTS:
            try:
                helptext = self.ARG_DICT[argument]['help']
                converter = self.ARG_DICT[argument].get("converter", str)
                i = input("    %s> " % helptext)
                if i:
                    if i.lower() == 'none':
                        i = ''
                    input_values[argument] = converter(i)
            except EOFError:
                print("")
                exit = 'y'
                exit = input("Do you really want to exit ([y]/n)? ")
                if exit == 'y':
                    sys.exit(0)

        print("These fields will be changed:")
        print(input_values)
        if delete:
            if self._confirm_delete():
                self.delete(**input_values)
        else:
            save = input("Save to config (y/[n])? ")
            if save in ['y', 'Y', 'yes', 'Yes', 'YES']:
                self.run(**input_values)
            else:
                print("Not saved.")

    @classmethod
    def run_cmd(klass, config, kwargs, delete):
        """
        Method to be invoked by parser upon invocation of specific command.
        """
        self = klass(config)

        if kwargs:
            if delete:
                if self._confirm_delete():
                    self.delete(**kwargs)
            else:
                self.run(**kwargs)
        else:
            if delete and not getattr(self, 'interactive_delete', True):
                # special method to handle this combination of options to avoid mistakes
                self.non_interactive_delete(**kwargs)
            else:
                self.interactive_mode(delete)

    def non_interactive_delete(**kwargs):
        """
        To be used in the case where 'self.interactive_delete' is False.
        """
        raise AutobuildError("Delete not yet implemented for this command.")

    def delete(self, **kwargs):
        """
        Stub for the delete command.
        """
        raise AutobuildError("Delete not yet implemented for this command.")

    def _confirm_delete(self):
        really_delete = input("Do you really want to delete this entry (y/[n])? ")
        if really_delete in ['y', 'Y', 'yes', 'Yes', 'YES']:
            return True
        return False
