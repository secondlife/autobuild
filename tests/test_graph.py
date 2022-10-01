import logging
import os
import tempfile

import pytest

from tests.basetest import temp_dir

try:
    import pydot
    with temp_dir() as d:
        g = pydot.graph_from_dot_data('graph g {}')[0]
        g.write_png(os.path.join(d, "graph.png"))
        pydot_available = True
except (ImportError, FileNotFoundError):
    pydot_available = False

import autobuild.autobuild_tool_graph as graph
import autobuild.common as common
from tests.basetest import *

logger = logging.getLogger(__name__)


class GraphOptions(object):
    def __init__(self):
        self.source_file = None
        self.graph_type='dot'
        self.display=False
        self.graph_file=None
        self.dot_file=None
        self.platform=None
        self.addrsize=common.DEFAULT_ADDRSIZE


@pytest.mark.skipif(not pydot_available, reason="pydot not available")
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

    def test_dot_output(self):
        self.tmp_dir = tempfile.mkdtemp()
        try:
            self.options.dot_file = os.path.join(self.tmp_dir, "graph.dot")
            self.options.source_file = os.path.join(self.this_dir, "data", "bongo-0.1-common-111.tar.bz2")
            graph.AutobuildTool().run(self.options)
            assert os.path.exists(self.options.dot_file)

        finally:
            clean_dir(self.tmp_dir)

    def test_png_output(self):
        self.tmp_dir = tempfile.mkdtemp()
        try:
            self.options.graph_file = os.path.join(self.tmp_dir, "graph.png")
            self.options.source_file = os.path.join(self.this_dir, "data", "bongo-0.1-common-111.tar.bz2")
            graph.AutobuildTool().run(self.options)
            assert os.path.exists(self.options.graph_file)

        finally:
            clean_dir(self.tmp_dir)

    def test_jpeg_output(self):
        self.tmp_dir = tempfile.mkdtemp()
        try:
            self.options.graph_file = os.path.join(self.tmp_dir, "graph.jpeg")
            self.options.source_file = os.path.join(self.this_dir, "data", "bongo-0.1-common-111.tar.bz2")
            graph.AutobuildTool().run(self.options)
            assert os.path.exists(self.options.graph_file)

        finally:
            clean_dir(self.tmp_dir)

    def test_svg_output(self):
        self.tmp_dir = tempfile.mkdtemp()
        try:
            self.options.graph_file = os.path.join(self.tmp_dir, "graph.svg")
            self.options.source_file = os.path.join(self.this_dir, "data", "bongo-0.1-common-111.tar.bz2")
            graph.AutobuildTool().run(self.options)
            assert os.path.exists(self.options.graph_file)

        finally:
            clean_dir(self.tmp_dir)

    def tearDown(self):
        BaseTest.tearDown(self)


class TestMermaidGraph(BaseTest):
    def setUp(self):
        BaseTest.setUp(self)
        self.options=GraphOptions()
        self.options.graph_type = 'mermaid'

    def test_output(self):
        with CaptureStdout() as out:
            self.options.source_file = os.path.join(self.this_dir, "data", "bongo-0.1-common-111.tar.bz2")
            graph.AutobuildTool().run(self.options)
        graph_txt = out.getvalue()
        self.assertIn('graph TB', graph_txt)
        self.assertIn('bongo<br />1<br />111', graph_txt)
        self.assertIn('bingo<br />0.2<br />222', graph_txt)

    def tearDown(self):
        BaseTest.tearDown(self)
