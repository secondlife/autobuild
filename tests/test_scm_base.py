# $LicenseInfo:firstyear=2022&license=mit$
# Copyright (c) 2022, Linden Research, Inc.
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

import pytest

from autobuild.scm.base import Semver


@pytest.mark.parametrize("input,want", [
    ("v1.0.0", "1.0.0"),
    ("v1", "1.0.0"),
    ("1", "1.0.0"),
    ("v1.0", "1.0.0"),
    ("v1.0.0-alpha1", "1.0.0-alpha1"),
    ("v1.0.0-", "1.0.0"),
    ("hotdog", "None"),
])
def test_semver(input, want):
    assert str(Semver.parse(input)) == want


@pytest.mark.parametrize("input,want", [
    ("v1.0.0", "1.0.1"),
    ("v1.0.0-", "1.0.1"),
    ("v1.0.0-alpha1", "1.0.0"),
])
def test_semver_next(input, want):
    assert str(Semver.parse(input).next) == want