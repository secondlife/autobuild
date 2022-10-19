"""
Graph the dependencies of a package.

This autobuild sub-command will read an autobuild metadata file and produce a graph of
the dependencies of the project.
"""

import logging
import os
import tempfile
import webbrowser
from io import StringIO
from typing import NamedTuple

from autobuild import autobuild_base, common, configfile
from autobuild.autobuild_tool_install import get_metadata_from_package

logger = logging.getLogger('autobuild.graph')


class GraphError(common.AutobuildError):
    pass

__help = """\
This autobuild command displays a dependecy graph for a package.

You may either:
  1) not specify a file - attempts to show dependencies of the current build tree
  2) specify an xml file - interprets the file as an autobuild-package metadata file
                        and displays its dependencies
  3) specify a package file - extracts the metadata from the package and displays
                              the dependencies of the package

The --rebuild-from <package-name> option prints an ordered list of packages that
must be rebuilt if the specified package is updated.
"""

class MermaidBracket(NamedTuple):
    """Mermaid graph bracket type"""
    start: str
    end: str


class MermaidBrackets:
    Stadium = MermaidBracket('([', '])')
    Hexagon = MermaidBracket('{{', '}}')
    Box = MermaidBracket('[', ']')


# define the entry point to this autobuild tool
class AutobuildTool(autobuild_base.AutobuildBase):
    def get_details(self):
        return dict(name=self.name_from_file(__file__),
                    description='Graph package dependencies.')

    def register(self, parser):
        parser.description = "Graph package dependencies."
        parser.add_argument('source_file',
                            nargs="?",
                            default=None,
                            help='package or metadata file.')
        parser.add_argument('--config-file',
                            dest='config_filename',
                            default=configfile.AUTOBUILD_CONFIG_FILE,
                            help="The file used to describe what should be installed and built\n  (defaults to $AUTOBUILD_CONFIG_FILE or \"autobuild.xml\").")
        parser.add_argument('--configuration', '-c',
                            dest='configuration',
                            help="specify build configuration\n(may be specified in $AUTOBUILD_CONFIGURATION)",
                            metavar='CONFIGURATION',
                            default=self.configurations_from_environment())
        parser.add_argument('-t', '--type',
                            dest='graph_type',
                            choices=["dot", "circo", "neato", "twopi", "fdp", "sfdp", "mermaid"],
                            default='dot',
                            help='which graphviz tool should be used to draw the graph')
        parser.add_argument('--install-dir',
                            default=None,
                            dest='select_dir',          # see common.select_directories()
                            help='Where installed files were unpacked.')
        parser.add_argument('--installed-manifest',
                            default=configfile.INSTALLED_CONFIG_FILE,
                            dest='installed_filename',
                            help='The file used to record what is installed.')
        parser.add_argument('--no-display',
                            dest='display', action='store_false', default=True,
                            help='do not generate and display graph; output dot file on stdout instead')
        parser.add_argument('--graph-file', '-g',
                            dest='graph_file', default=None,
                            help='do not display graph; store graph file in the specified file')
        parser.add_argument('--dot-file', '-D',
                            dest='dot_file', default=None,
                            help='save the dot input file in the specified file')
    def run(self, args):
        platform=common.get_current_platform()
        metadata = None
        incomplete = ''
        if not args.source_file:
            # no file specified, so assume we are in a build tree and find the
            # metadata in the current build directory
            logger.info("searching for metadata in the current build tree")
            config_filename = args.config_filename
            config = configfile.ConfigurationDescription(config_filename)
            metadata_file = os.path.join(config.get_build_directory(args.configuration, platform), configfile.PACKAGE_METADATA_FILE)
            if not os.path.exists(metadata_file):
                logger.warning("No complete metadata file found; attempting to use partial data from installed files")
                # get the absolute path to the installed-packages.xml file
                args.all = False
                args.configurations = args.configuration
                install_dirs = common.select_directories(args, config, "install", "getting installed packages",
                                                         lambda cnf:
                                                         os.path.join(config.get_build_directory(cnf, platform), "packages"))
                installed_pathname = os.path.join(os.path.realpath(install_dirs[0]), args.installed_filename)
                if os.path.exists(installed_pathname):
                    # dummy up a metadata object, but don't create the file
                    metadata = configfile.MetadataDescription()
                    # use the package description from the configuration
                    metadata.package_description = config.package_description
                    metadata.add_dependencies(installed_pathname)
                    incomplete = ' (possibly incomplete)'
                else:
                    raise GraphError("No metadata found in current directory")
            else:
                metadata = configfile.MetadataDescription(path=metadata_file)
        elif args.source_file.endswith(".xml"):
            # the specified file is an xml file; assume it is a metadata file
            logger.info("searching for metadata in autobuild package metadata file %s" % args.source_file)
            metadata = configfile.MetadataDescription(path=args.source_file)
            if not metadata:
                raise GraphError("No metadata found in '%s'" % args.source_file)
        else:
            # assume that the file is a package archive and try to get metadata from it
            logger.info("searching for metadata in autobuild package file %s" % args.source_file)
            metadata = get_metadata_from_package(args.source_file)
            if not metadata:
                raise GraphError("No metadata found in archive '%s'" % args.source_file)

        if not metadata:
            raise GraphError("No metadata found")

        if args.graph_type == 'mermaid':
            sb = StringIO()
            sb.write('graph TB')

            connections = set()
            def add_depends(sb: StringIO, pkg, root = False):
                name = pkg['package_description']['name']
                version = pkg['package_description']['version'] if pkg['package_description']['version'] else ""
                build_id = pkg['build_id'] if pkg['build_id'] else ""
                dirty = pkg.get('dirty', False) in ('True', True)
                id = hash(name)

                if dirty:
                    bracket = MermaidBrackets.Stadium
                elif root:
                    bracket = MermaidBrackets.Hexagon
                else:
                    bracket = MermaidBrackets.Box

                sb.write(f'\n    {id}{bracket.start}"{name}<br />{version}<br />{build_id}"{bracket.end}')

                archive = pkg.get('archive')
                if archive:
                    # Link to the archive URL
                    url = pkg['archive']['url']
                    sb.write(f'\n    click {id} "{url}"')

                for dep_pkg in pkg.get('dependencies', {}).values():
                    dep_name = dep_pkg['package_description']['name']
                    dep_id = hash(dep_name)
                    dep_dirty = dep_pkg.get('dirty', False) in ('True', True)
                    # Draw dirty connections with dotted line
                    arrow = '-.->' if dep_dirty else '-->'
                    connection = f"{dep_id}-{pkg['build_id']}"
                    if connection not in connections:
                        add_depends(sb, dep_pkg)
                        sb.write(f'\n    {dep_id}{arrow}{id}')
                        connections.add(connection)

            add_depends(sb, metadata, root=True)
            print(sb.getvalue())
        else:
            import pydot
            graph = pydot.Dot(label=metadata['package_description']['name']+incomplete+' dependencies for '+platform, graph_type='digraph')
            graph.set('overlap', 'false')
            graph.set('splines', 'true')
            graph.set('scale', '2')
            graph.set('smoothType', 'spring')
            graph.set('labelloc', 'top')
            graph.set('labeljust', 'center')

            graph.set_node_defaults(shape='box')

            def add_depends(graph, pkg):
                name = pkg['package_description']['name']
                got = graph.get_node(name) # can return a single Node instance, a list of Nodes, or None
                try:
                    pkg_node = got if got is None or isinstance(got, pydot.Node) else got[0]
                except IndexError: # some versions of pydot may return an empty list instead of None
                    pkg_node = None
                if pkg_node is None:
                    logger.debug(" graph adding package %s" % name)
                    # can't use the dict .get to supply an empty string default for these,
                    # because the value in the dict is None.
                    pkg_version = pkg['package_description']['version'] if pkg['package_description']['version'] else "";
                    pkg_build_id = pkg['build_id'] if pkg['build_id'] else "";
                    # create the new node with name, version, and build id
                    pkg_node = pydot.Node(name, label="%s\\n%s\\n%s" % (name, pkg_version, pkg_build_id))
                    if 'dirty' in pkg and (pkg['dirty'] == 'True' or pkg['dirty'] is True):
                        logger.debug(" setting %s dirty: %s" % (name, ("missing" if 'dirty' not in pkg else "explicit")))
                        pkg_node.set_shape('ellipse')
                        pkg_node.set_style('dashed')
                    graph.add_node(pkg_node)
                    if 'dependencies' in pkg:
                        for dep_pkg in pkg['dependencies'].values():
                            dep_name = dep_pkg['package_description']['name']
                            dep_node = add_depends(graph, dep_pkg)
                            logger.debug(" graph adding dependency %s -> %s" % (dep_name, name))
                            edge = pydot.Edge(dep_name, name)
                            if 'dirty' in dep_pkg and (dep_pkg['dirty'] == 'True' or dep_pkg['dirty'] is True):
                                edge.set_style('dashed')
                            graph.add_edge(edge)
                return pkg_node

            root = add_depends(graph, metadata)
            root.set_root('true')
            root.set_shape('octagon')

            if args.dot_file:
                graph.write_raw(args.dot_file)

            if args.display or args.graph_file:
                if args.graph_file:
                    graph_file = args.graph_file
                else:
                    graph_file = os.path.join(tempfile.gettempdir(),
                                                metadata['package_description']['name'] + "_graph_"
                                                + args.graph_type + '.png')
                logger.info("writing %s" % graph_file)
                if graph_file.endswith('.svg'):
                    graph.write_svg(graph_file, prog=args.graph_type)
                elif graph_file.endswith('.jpeg'):
                    graph.write_jpeg(graph_file, prog=args.graph_type)
                else:
                    graph.write_png(graph_file, prog=args.graph_type)
                if args.display and not args.graph_file:
                    webbrowser.open('file:'+graph_file)
            else:
                print("%s" % graph.to_string())
