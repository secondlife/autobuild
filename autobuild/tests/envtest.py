# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$

import os
import sys

if __name__ == '__main__':
    # verify that the AUTOBUILD env var is set to point to something executable
    assert os.access(os.environ['AUTOBUILD'], os.X_OK)
    sys.exit(0)
