import os


def setup():
    os.environ.pop('AUTOBUILD_CONFIGURATION', None)
