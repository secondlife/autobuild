@echo off
rem simple wrapper for executing autobuild on windows.

set dirname=%~p0
python "%dirname%autobuild" %*
