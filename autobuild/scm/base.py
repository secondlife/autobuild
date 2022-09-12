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
from __future__ import annotations

import os
import subprocess
from datetime import datetime
from typing import NamedTuple, Union


def cmd(*cmd, **kwargs) -> subprocess.CompletedProcess[str]:
    p = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, text=True, **kwargs)
    p.stdout = p.stdout.rstrip("\n")
    return p


def has_command(name) -> bool:
    try:
        p = cmd(name, "help")
    except OSError:
        return False
    return not p.returncode


def date() -> str:
    return datetime.now().strftime("%Y%m%d")


def is_env_disabled(key: str) -> bool:
    """Check whether an envvar has an explicit falsey value. Useful for opt-out behavior."""
    return os.environ.get(key, "true") in {"false", "0", "f", "no"}


class Semver(NamedTuple):
    major: int
    minor: int
    patch: int
    prerelease: str

    @property
    def next(self) -> "Semver":
        return Semver(
            major=self.major,
            minor=self.minor,
            patch=self.patch if self.prerelease else self.patch + 1,
            prerelease=None,
        )

    def __str__(self) -> str:
        if self.prerelease:
            return f"{self.major}.{self.minor}.{self.patch}-{self.prerelease}"
        return f"{self.major}.{self.minor}.{self.patch}"

    @staticmethod
    def parse(v: str) -> Union[None, "Semver"]:
        if v.startswith("v"):
            v = v[1:]

        split = v.split(".")

        # Extract pre-release
        last = split[-1]
        prerelease = None
        try:
            prerelease_idx = last.index("-")
            prerelease = last[prerelease_idx+1:]
            split[-1] = last[:prerelease_idx]
        except ValueError:
            pass

        # Populate all version numbers, even if only one or two is provided, ex. v1 or v1.0
        try:
            major, minor, patch = (int(split[i]) if i < len(split) else 0 for i in range(3))
        except ValueError:
            return None

        return Semver(
            major=major,
            minor=minor,
            patch=patch,
            prerelease=prerelease,
        )

