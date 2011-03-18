rem @echo off
rem simple wrapper for executing extensionless python script on windows.
echo hello world
python -v "%~dpn0" %*
