import os
import sys

from autobuild.executable import Executable

_SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))


def echo(text):
    return Executable(command=sys.executable, options=[os.path.join(_SCRIPT_DIR, "echo.py")], arguments=[text])


# Formally you might consider that noop.py and envtest.py are "arguments" rather
# than "options" -- but the way Executable is structured, if we pass
# them as "argument" then the "build" subcommand gets inserted before,
# which thoroughly confuses the Python interpreter.
noop = Executable(command=sys.executable, options=[os.path.join(_SCRIPT_DIR, "noop.py")])
envtest = Executable(command=sys.executable, options=[os.path.join(_SCRIPT_DIR, "envtest.py")])
