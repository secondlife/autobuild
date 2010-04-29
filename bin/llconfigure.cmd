@echo off
rem simple wrapper for executing configure on windows.

set dirname=%~p0
python "%dirname%llconfigure" %*
