"""
Provides tools for manipulating platform manifests.

Manifests specify by platform the files that should be bundled into
an archive when packaging the build product.
"""

from autobuild import autobuild_base, common, configfile


class AutobuildTool(autobuild_base.AutobuildBase):
    def get_details(self):
        return dict(name=self.name_from_file(__file__),
                    description="Manipulate manifest entries to the autobuild configuration.")

    def register(self, parser):
        parser.description = "specify manifest of artifacts to be packaged by the 'autobuild package' command."
        parser.add_argument('--config-file',
                            dest='config_file',
                            default=configfile.AUTOBUILD_CONFIG_FILE,
                            help='(defaults to $AUTOBUILD_CONFIG_FILE or "autobuild.xml")')
        parser.add_argument('command', nargs='?', default='print',
                            help="manifest command: add, remove, clear, or print")
        parser.add_argument('pattern', nargs='*', help='a file pattern')

    def run(self, args):
        platform=common.get_current_platform()
        config = configfile.ConfigurationDescription(args.config_file)
        if args.command == 'add':
            [add(config, platform, p) for p in args.pattern]
        elif args.command == 'remove':
            [remove(config, platform, p) for p in args.pattern]
        elif args.command == 'clear':
            clear(config, platform)
        elif args.command == 'print':
            print_manifest(config, platform)
        else:
            raise ManifestError('unknown command %s' % args.command)
        if not args.dry_run:
            config.save()


class ManifestError(common.AutobuildError):
    pass


def add(config, platform_name, pattern):
    """
    Adds a pattern to the giving platform's manifest.
    """
    platform_description = config.get_platform(platform_name)
    platform_description.manifest.append(pattern)


def remove(config, platform_name, pattern):
    """
    Removes first occurrence of a pattern in the manifest which is equivalent to the given pattern.
    """
    platform_description = config.get_platform(platform_name)
    try:
        platform_description.manifest.remove(pattern)
    except ValueError:  # platform_description.manifest does not contain 'pattern'
        pass


def clear(config, platform_name):
    """
    Clears all entries from the manifest list.
    """
    config.get_platform(platform_name).manifest = []


def print_manifest(config, platform_name):
    """
    Prints the platform's manifest.
    """
    if platform_name == 'all':
        for platform in config.get_all_platforms():
            patterns = config.get_platform(platform).manifest
            if len(patterns) == 0:
                continue
            print("%s:" % platform)
            for pattern in config.get_platform(platform).manifest:
                print("\t%s" % pattern)
    else:
        for pattern in config.get_platform(platform_name).manifest:
            print(pattern)
