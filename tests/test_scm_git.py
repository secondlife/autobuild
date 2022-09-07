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

import os
import tempfile
from contextlib import contextmanager
from unittest import TestCase

import pytest

from autobuild.scm.base import cmd, date, has_command
from autobuild.scm.git import get_version
from tests.basetest import chdir

pytestmark = pytest.mark.skipif(not has_command("git"), reason="git not found")


@contextmanager
def git_repo():
    """
    Initialize a new git repository in a temporary directory, yield its path, clean after context exit.

    Layout:
        .
        ├── dir
        │   └── file
        ├── file
        ├── .gitignore
        └── stage
    """
    owd = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as root:
            os.chdir(root)
            with open(os.path.join(root, "file"), "w"):
                pass
            os.mkdir(os.path.join(root, "dir"))
            with open(os.path.join(root, "dir", "file"), "w"):
                pass
            os.mkdir(os.path.join(root, "stage"))
            with open(os.path.join(root, ".gitignore"), "w") as f:
                f.write("stage")
            cmd("git", "init")
            cmd("git", "add", "-A")
            cmd("git", "commit", "-m", "Initial")
            cmd("git", "tag", "v1.0.0")
            yield root
    finally:
        os.chdir(owd)


class GitTests(TestCase):
    repo: str

    @pytest.fixture(autouse=True)
    def init(self):
        with git_repo() as repo:
            self.repo = repo
            yield

    def test_no_distance_clean(self):
        version = get_version(self.repo)
        self.assertEqual(version, "1.0.0")

    def test_no_distance_clean_from_stage(self):
        with chdir(os.path.join(self.repo, "stage")):
            version = get_version(self.repo)
            self.assertEqual(version, "1.0.0")

    def test_no_distance_clean_child(self):
        # Test that SCM searches for .git dir in parent directories
        path = os.path.join(self.repo, "dir")
        version = get_version(path)
        self.assertEqual(version, "1.0.0")

    def test_hotdog(self):
        version = get_version(self.repo)
        cmd("git", "tag", "hotdog")
        self.assertEqual(version, "1.0.0")

    def test_distance_clean(self):
        with open(os.path.join(self.repo, "file"), "w") as f:
            f.write("+1")
        cmd("git", "add", "file")
        cmd("git", "commit", "-m", "distance")
        version = get_version(self.repo)
        self.assertRegex(version, r"^1\.0\.1\-dev1\.g[a-z0-9]{7}$")

    def test_no_distance_clean_with_prerelease(self):
        with open(os.path.join(self.repo, "file"), "w") as f:
            f.write("+1")
        cmd("git", "add", "file")
        cmd("git", "commit", "-m", "distance")
        cmd("git", "tag", "v2.0.0-alpha1")
        version = get_version(self.repo)
        self.assertEqual(version, "2.0.0-alpha1")

    def test_distance_clean_with_prerelease(self):
        with open(os.path.join(self.repo, "file"), "w") as f:
            f.write("+1")
        cmd("git", "add", "file")
        cmd("git", "commit", "-m", "distance")
        cmd("git", "tag", "v2.0.0-alpha1")
        with open(os.path.join(self.repo, "file"), "w") as f:
            f.write("+2")
        cmd("git", "add", "file")
        cmd("git", "commit", "-m", "distance")
        version = get_version(self.repo)
        self.assertRegex(version, r"^2\.0\.0\-dev1\.g[a-z0-9]{7}$")

    def test_distance_clean_with_major(self):
        with open(os.path.join(self.repo, "file"), "w") as f:
            f.write("+1")
        cmd("git", "tag", "v1")
        cmd("git", "add", "file")
        cmd("git", "commit", "-m", "distance")
        version = get_version(self.repo)
        self.assertRegex(version, r"^1\.0\.1\-dev1\.g[a-z0-9]{7}$")

    def test_no_distance_dirty(self):
        with open(os.path.join(self.repo, "file"), "w") as f:
            f.write("+1")
        cmd("git", "add", "file")
        version = get_version(self.repo)
        self.assertRegex(version, fr"^1\.0\.1\-dev0\.g[a-z0-9]{{7}}.d{date()}$")

    def test_distance_dirty(self):
        # Add distance
        with open(os.path.join(self.repo, "file"), "w") as f:
            f.write("+1")
        cmd("git", "add", "file")
        cmd("git", "commit", "-m", "distance")
        # Make dirty
        with open(os.path.join(self.repo, "file"), "w") as f:
            f.write("+2")
        cmd("git", "add", "file")
        version = get_version(self.repo)
        self.assertRegex(version, fr"^1\.0\.1\-dev1\.g[a-z0-9]{{7}}.d{date()}$")