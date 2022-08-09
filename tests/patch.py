#!/usr/bin/python
"""\
@file   patch.py
@author Nat Goodspeed
@date   2014-09-05
@brief  Ability to temporarily patch an attribute in some other module.

$LicenseInfo:firstyear=2014&license=mit$
Copyright (c) 2014, Linden Research, Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
$/LicenseInfo$
"""

import contextlib


@contextlib.contextmanager
def patch(module, attribute, value):
    """
    Usage:

    # assert configfile.AUTOBUILD_CONFIG_VERSION == "1.3"
    with patch(configfile, "AUTOBUILD_CONFIG_VERSION", "1.5"):
        # assert configfile.AUTOBUILD_CONFIG_VERSION == "1.5"
        # ...
    # assert configfile.AUTOBUILD_CONFIG_VERSION == "1.3" again
    """
    try:
        # what's the current value of the attribute?
        saved = getattr(module, attribute)
    except AttributeError:
        # doesn't exist, we're adding it, so delete it later
        restore = lambda: delattr(module, attribute)
    else:
        # 'saved' is prev value, so reset to 'saved' later
        restore = lambda: setattr(module, attribute, saved)

    try:
        # set the desired module attribute
        setattr(module, attribute, value)
        # run body of 'with' block
        yield
    finally:
        # no matter how we leave, restore to previous state
        restore()
