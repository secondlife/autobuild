import os
import tempfile
from contextlib import contextmanager
from unittest import TestCase

import pytest

from autobuild.util import cmd, has_cmd
from autobuild.scm.base import date
from autobuild.scm.git import get_version
from tests.basetest import chdir, git_repo

pytestmark = pytest.mark.skipif(not has_cmd("git"), reason="git not found")


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
