#!/usr/bin/python
# $LicenseInfo:firstyear=2014&license=mit$
# Copyright (c) 2014, Linden Research, Inc.
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
Graph the dependencies of a package.

This autobuild sub-command will read an autobuild metadata file and produce a graph of 
the dependencies of the project.

Author : Scott Lawrence / Logan Dethrow
Date   : 2014-05-09
"""

import os
import sys
import pprint
import tempfile

import pydot
import webbrowser

import common
import logging
import configfile
import autobuild_base
from autobuild_tool_install import extract_metadata_from_package

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
        parser.add_argument('-p', '--platform',
                            dest='platform',
                            default=common.get_current_platform(),
                            help='override the working platform')
        parser.add_argument('-t','--type', 
                            dest='graph_type',
                            choices=["dot","circo","neato","twopi","fdp","sfdp"],
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

    def run(self, args):
        metadata = None
        incomplete = ''
        if args.source_file is None:
            # no file specified, so assume we are in a build tree and find the 
            # metadata in the current build directory
            logger.info("searching for metadata in the current build tree")
            config_filename = args.config_filename
            config = configfile.ConfigurationDescription(config_filename)
            metadata_file = os.path.join(config.get_build_directory(args.configuration, args.platform), configfile.PACKAGE_METADATA_FILE)
            if not os.path.exists(metadata_file):
                logger.warning("No complete metadata file found; attempting to use partial data from installed files")
                # get the absolute path to the installed-packages.xml file
                args.all = False
                args.configurations=(args.configuration)
                install_dirs = common.select_directories(args, config, "install", "getting installed packages",
                                                         lambda cnf:
                                                         os.path.join(config.get_build_directory(cnf, args.platform), "packages"))
                installed_pathname = os.path.join(os.path.realpath(install_dirs[0]), args.installed_filename)
                if os.path.exists(installed_pathname):
                    # dummy up a metadata object, but don't create the file
                    metadata=configfile.MetadataDescription()
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
            metadata_stream=extract_metadata_from_package(args.source_file, configfile.PACKAGE_METADATA_FILE)
            if metadata_stream is not None:
                metadata = configfile.MetadataDescription(stream=metadata_stream)
                if not metadata:
                    raise GraphError("No metadata found in archive '%s'" % args.file)
            
        if metadata:
            graph=pydot.Dot(label=metadata['package_description']['name']+incomplete+' dependencies', graph_type='digraph')
            graph.set('overlap','false')
            graph.set('splines','true')
            graph.set('scale','2')
            graph.set('smoothType','spring')
            graph.set('labelloc','top')
            graph.set('labeljust','center')

            graph.set_node_defaults(shape='box')

            seen=dict()
            def add_depends(graph, pkg):
                name=pkg['package_description']['name']
                try:
                    pkg_node = graph.get_node(name)[0]
                except IndexError:
                    pkg_node = None
                if pkg_node is None:
                    logger.debug(" graph adding package %s" % name)
                    pkg_node=pydot.Node(name)
                    if 'dirty' in pkg and ( pkg['dirty'] == 'True' or pkg['dirty'] == True ):
                        logger.debug(" setting %s dirty: %s" % (name, ("missing" if 'dirty' not in pkg else "explicit")))
                        pkg_node.set_shape('ellipse')
                        pkg_node.set_style('dashed')
                    graph.add_node(pkg_node)
                    if 'dependencies' in pkg:
                        for dep_pkg in pkg['dependencies'].itervalues():
                            dep_name=dep_pkg['package_description']['name']
                            dep_node=add_depends(graph, dep_pkg)
                            logger.debug(" graph adding dependency %s -> %s" % (dep_name, name))
                            edge=pydot.Edge(dep_name, name)
                            if 'dirty' not in dep_pkg or dep_pkg['dirty'] == 'True' or dep_pkg['dirty'] == True:
                                edge.set_style('dashed')
                            graph.add_edge(edge)
                return pkg_node

            root=add_depends(graph, metadata)
            root.set_root('true')
            root.set_shape('octagon')
            
            logger.debug("dot:\n"+graph.to_string())

            graph_file=os.path.join(tempfile.gettempdir(),metadata['package_description']['name'] + "_graph_" + args.graph_type + '.png')

            logger.info("writing %s" % graph_file)
            graph.write_png(graph_file, prog=args.graph_type)

            webbrowser.open('file:'+graph_file)

        else:
            logger.error("No metadata found")
        

if __name__ == '__main__':
    sys.exit("Please invoke this script using 'autobuild %s'" %
             AutobuildTool().get_details()["name"])
