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

"""
If a version_file attribute is not present in autobuild.xml then autobuild will
attempt to resolve package version from source control management (SCM) metadata.
Only git is supported at this time.

## Versioning scheme

Autobuild SCM version behavior takes the following into consideration:

- The latest tag with a version number
- The distance from this tag
- Whether the environment is "dirty" (has uncommitted changes)

This information is used to construct a version:

- clean with no distance: {current}
- clean with distance:    {next}-dev{distance}.g{revision}
- dirty:                  {next}-dev{distance}.g{revision}.d{YYYYMMDD}

The {next} tag is the current semver value + a patch bump, ex. 1.0.0 -> 1.0.1

This behavior closely matches setuptools_scm, deviating to match Semantic
Versioning rather than PEP 440

## Environment variables

SCM version resolution can be disabled by setting the following environment
variables to a falsey value (0, f, no, false)

- AUTOBUILD_SCM        - disable SCM version resolution
- AUTOBUILD_SCM_SEARCH - disable walking up parent directories to search for SCM root
"""

import subprocess
import logging
from pathlib import Path
from typing import NamedTuple

from autobuild.scm.base import cmd, has_command, date, is_env_disabled, Semver


__all__ = ["get_version"]


log = logging.getLogger(__name__)


MAX_GIT_SEARCH_DEPTH = 20


class GitMeta(NamedTuple):
    dirty: bool
    distance: int
    commit: str # Short commit hash 
    version: Semver


def _find_git_dir(start: str, level: int = 0) -> str | None:
    """Walk up path to find .git directory"""
    if level >= MAX_GIT_SEARCH_DEPTH:
        return None
    dir = Path(start) / ".git"
    if dir.is_dir(): 
        return str(dir)
    # Allow user to disable searching parent directories
    if is_env_disabled("AUTOBUILD_SCM_SEARCH"):
        return None
    return _find_git_dir(dir.parent.parent, level + 1)


def _parse_describe(describe: str) -> GitMeta:
    """Parse git describe output"""
    # describe looks like 'v2.0.0-0-gc688c51' or 'v2.0.0-0-gc688c51-dirty'
    log.debug(f"parsing git describe {describe}")
    dirty = False
    if describe.endswith("-dirty"):
        dirty = True
        describe = describe[:-6]

    raw_tag, distance, commit = describe.rsplit("-", 2)

    return GitMeta(
        dirty=dirty,
        distance=int(distance),
        commit=commit[1:], # omit "g" prefix
        version=Semver.parse(raw_tag),
    )


class Git:
    git_dir: str

    def __init__(self, root: str):
        self.git_dir = _find_git_dir(root) 

    def _git(self, *args) -> subprocess.CompletedProcess[str]:
        """Run git subcommand against the active git directory"""
        log.debug(f'running git command: {" ".join(args)}')
        return cmd("git", "--git-dir", self.git_dir, *args)
    
    def describe(self) -> str:
        # from https://github.com/pypa/setuptools_scm/blob/main/src/setuptools_scm/git.py
        p = self._git("describe", "--dirty", "--tags", "--long", "--match", "*[0-9]*")
        return p.stdout
    
    def version(self) -> str | None:
        # If git_dir is not set then we were unable to find a .git directory
        if not self.git_dir:
            log.debug("no git root found, returning null version")
            return None
        meta = _parse_describe(self.describe())

        if meta.dirty:
            # dirty + distance or no distance
            return f"{meta.version.next}-dev{meta.distance}.g{meta.commit}.d{date()}"
        elif meta.distance:
            # clean + distance
            return f"{meta.version.next}-dev{meta.distance}.g{meta.commit}"
        else:
            # clean + no distance
            return str(meta.version)


def get_version(root: str) -> str | None:
    """
    Attempt to resolve package version from git commit data.
    """
    if is_env_disabled("AUTOBUILD_SCM"):
        log.debug("SCM version detection disabled, skipping")
        return None
    if not has_command("git"):
        log.debug("git command not available, skipping git version detection")
        return None
    return Git(root).version()