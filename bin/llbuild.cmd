@echo off
rem simple wrapper for executing build on windows.

set dirname=%~dp0
python "%dirname%llbuild" %*
