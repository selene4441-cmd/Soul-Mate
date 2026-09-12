from functools import partial
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import shutil
import subprocess
import threading
import unittest
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "demo"
INDEX_PATH = DEMO_DIR / "index.html"
STYLES_PATH = DEMO_DIR / "styles.css"
SCRIPT_PATH = DEMO_DIR / "app.js"


class AssetCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.screens = set()
        self.stylesheets = []
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if "id" in values:
            self.ids.add(values["id"])
        if "data-screen" in values:
            self.screens.add(values["data-screen"])
        if tag == "link" and values.get("rel") == "stylesheet":
            self.stylesheets.append(values.get("href", ""))
        if tag == "script" and values.get("src"):
            self.scripts.append(values["src"])


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


class DemoAssetsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = INDEX_PATH.read_text(encoding="utf-8")
        cls.css = STYLES_PATH.read_text(encoding="utf-8")
        cls.js = SCRIPT_PATH.read_text(encoding="utf-8")
        cls.parser = AssetCollector()
        cls.parser.feed(cls.html)

        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            partial(QuietHandler, directory=str(DEMO_DIR)),
        )
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_required_flow_screens_are_present(self):
        expected = {
            "welcome",
            "profile",
            "questions",
            "insights",
            "searching",
            "results",
            "candidate",
            "matched",
            "feedback",
        }
        self.assertEqual(expected, self.parser.screens)

    def test_local_assets_are_referenced(self):
        self.assertEqual(["styles.css"], self.parser.stylesheets)
        self.assertEqual(["app.js"], self.parser.scripts)
        remote_assets = [
            asset
            for asset in self.parser.stylesheets + self.parser.scripts
            if re.match(r"^https?://", asset)
        ]
        self.assertEqual([], remote_assets)

    def test_mock_data_and_key_dimensions_are_present(self):
        terms = [
            "steady-growth",
            "explore-together",
            "respect-space",
            "y_satisfaction",
            "成长方向",
            "时间与空间",
            "candidateScore",
        ]
        self.assertIn("const candidates", self.js)
        for term in terms:
            with self.subTest(term=term):
                self.assertIn(term, self.js)

    def test_responsive_layout_is_defined(self):
        self.assertIn("@media (max-width: 860px)", self.css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.css)

    def test_javascript_syntax(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is not installed")
        result = subprocess.run(
            [node, "--check", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_demo_is_served_over_http(self):
        base_url = f"http://127.0.0.1:{self.server.server_port}"
        for filename in ("index.html", "styles.css", "app.js"):
            with self.subTest(filename=filename):
                with urllib.request.urlopen(f"{base_url}/{filename}", timeout=5) as response:
                    self.assertEqual(200, response.status)
                    self.assertTrue(response.read())


if __name__ == "__main__":
    unittest.main()