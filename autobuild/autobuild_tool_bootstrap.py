import configfile
from autobuild_base import AutobuildBase
from common import AutobuildError, get_current_platform
from interactive import InteractiveCommand
from autobuild_tool_edit import Package, Configure, Build

CONFIG_NAME_DEFAULT='default'
DEFAULT_CONFIG_CMD=''
DEFAULT_BUILD_CMD=''

class AutobuildTool(AutobuildBase):

    def get_details(self):
        return dict(name=self.name_from_file(__file__),
            description="Bootstrap a new package configuration from scratch.")

    def register(self, parser):
        parser.add_argument('--config-file',
            dest='config_file',
            default=configfile.AUTOBUILD_CONFIG_FILE,
            help="")

    def run(self, args):
        config = configfile.ConfigurationDescription(args.config_file)
        print "Entering interactive mode."
        Package(config).interactive_mode()
        Configure(config).interactive_mode()
        Build(config).interactive_mode()

        if not args.dry_run:
            config.save()

