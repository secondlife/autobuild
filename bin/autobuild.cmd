@echo off
rem simple wrapper for executing autobuild on windows.

set dirname=%~dp0
python "%dirname%autobuild" %*
