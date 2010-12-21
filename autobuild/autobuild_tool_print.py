# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$
import configfile
from autobuild_base import AutobuildBase


class AutobuildTool(AutobuildBase):

    def get_details(self):
        return dict(name=self.name_from_file(__file__),
            description="Print configuration.")

    def register(self, parser):
        parser.add_argument('--config-file',
            dest='config_file',
            default=configfile.AUTOBUILD_CONFIG_FILE,
            help="")

    def run(self, args):
        config = configfile.ConfigurationDescription(args.config_file)
        configfile.pretty_print(config)


