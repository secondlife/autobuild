"""
@file   test_graph.py
@author Scott Lawrence
@date   2014-11-23
@brief  Test the dependency graph generation.

$LicenseInfo:firstyear=2014&license=mit$
Copyright (c) 2014, Linden Research, Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
$/LicenseInfo$
"""

import logging
import os
import tempfile

import pytest

try:
    import pydot
    with tempfile.TemporaryDirectory() as d:
        g = pydot.graph_from_dot_data('graph g {}')[0]
        g.write_png(os.path.join(d, "graph.png"))
except (ImportError, FileNotFoundError):
    pytest.skip("pydot not available", allow_module_level=True)
from unittest import TestCase

import autobuild.autobuild_tool_graph as graph
import autobuild.common as common

from .basetest import *

logger = logging.getLogger("test_graph")

class GraphOptions(object):
    def __init__(self):
        self.source_file = None
        self.graph_type='dot'
        self.display=False
        self.graph_file=None
        self.dot_file=None
        self.platform=None
        self.addrsize=common.DEFAULT_ADDRSIZE

class TestGraph(BaseTest):
    def setUp(self):
        BaseTest.setUp(self)
        self.options=GraphOptions()

    def test_nometa(self):
        with ExpectError("No metadata found", "no error detected when archive does not have metadata"):
            self.options.source_file = os.path.join(self.this_dir, "data", "nometa-0.1-common-111.tar.bz2")
            graph.AutobuildTool().run(self.options)

    def test_nopackage(self):
        with ExpectError("No metadata found", "no error detected when archive does not exist"):
            self.options.source_file = os.path.join(self.this_dir, "data", "nonexistant.tar.bz2")
            graph.AutobuildTool().run(self.options)

    def test_nodepends(self):
        self.options.source_file = os.path.join(self.this_dir, "data", "bingo-0.1-common-111.tar.bz2")
        output_lines=[]
        with CaptureStdout() as stream:
            graph.AutobuildTool().run(self.options)
            output_lines = stream.getvalue().splitlines()
        assert_found_in("label=\"bingo dependencies for ", output_lines) # omit platform
        assert_found_in("bingo \\[", output_lines)
        assert_not_found_in("->", output_lines)

    def test_depends(self):
        self.options.source_file = os.path.join(self.this_dir, "data", "bongo-0.1-common-111.tar.bz2")
        output_lines=[]
        with CaptureStdout() as stream:
            graph.AutobuildTool().run(self.options)
            output_lines = stream.getvalue().splitlines()
        assert_found_in("label=\"bongo dependencies for ", output_lines) # omit platform
        assert_found_in("bingo \\[", output_lines)
        assert_in("bingo -> bongo;", output_lines)

    def test_output(self):
        self.tmp_dir = tempfile.mkdtemp()
        try:
            self.options.graph_file = os.path.join(self.tmp_dir, "graph.png")
            self.options.dot_file = os.path.join(self.tmp_dir, "graph.dot")
            self.options.source_file = os.path.join(self.this_dir, "data", "bongo-0.1-common-111.tar.bz2")
            graph.AutobuildTool().run(self.options)
            # for now, settle for detecting that the png file was created
            assert os.path.exists(self.options.graph_file)
            assert os.path.exists(self.options.dot_file)

        finally:
            clean_dir(self.tmp_dir)

    def tearDown(self):
        BaseTest.tearDown(self)
