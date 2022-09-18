from autobuild import configfile
from autobuild.autobuild_base import AutobuildBase


class AutobuildTool(AutobuildBase):

    def get_details(self):
        return dict(name=self.name_from_file(__file__),
                    description="Print configuration.")

    def register(self, parser):
        parser.description = "provide a human-readable view of the package definition in the current package."
        parser.add_argument('--json', action='store_true', default=False, help='print config file contents using JSON')
        parser.add_argument('--config-file',
                            dest='config_file',
                            default=configfile.AUTOBUILD_CONFIG_FILE,
                            help='(defaults to $AUTOBUILD_CONFIG_FILE or "autobuild.xml")')

    def run(self, args):
        config = configfile.ConfigurationDescription(args.config_file)
        configfile.pretty_print(config, format='json' if args.json else 'pprint')
