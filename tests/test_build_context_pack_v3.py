import json
import tempfile
import unittest
from pathlib import Path

from scripts import build_context_pack_v3 as v3


def write(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class ManifestTests(unittest.TestCase):
    def test_manifest_reports_builder_version_v3(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "README.md", "# Example\n")
            v3.build_pack(root)
            manifest = json.loads((root / ".claude" / "project-context" / "MANIFEST.json").read_text(encoding="utf-8"))

        self.assertEqual("3.0.0", manifest["builder_version"])
        self.assertIn("import_graph", manifest["builder_features"])
        self.assertIn("query_routing", manifest["builder_features"])


class TaskRoutingStopwordsTests(unittest.TestCase):
    def test_task_routing_does_not_emit_stopwords(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "src/app/routes/billing.ts", "export function charge() {}\n")
            write(root, "src/app/routes/auth.ts", "export function login() {}\n")
            write(root, "tests/billing.test.ts", "test('charge', () => {});\n")
            files = v3.walk_files(root)
            areas = v3.build_areas(files)
            symbol_index = v3.build_symbol_index(root, files)
            routing = v3.build_task_routing(files, symbol_index, areas)

        for noise in ("src", "app", "routes", "tests"):
            self.assertNotIn(noise, routing, f"stopword '{noise}' leaked into task routing")
        self.assertIn("billing", routing)


class RouteQueryTests(unittest.TestCase):
    def test_route_query_writes_context_and_ranks_relevant_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "src/billing/charge.py", "def charge_customer():\n    return True\n")
            write(root, "src/billing/invoice.py", "def build_invoice():\n    return {}\n")
            write(root, "src/ui/dashboard.py", "def render_dashboard():\n    return ''\n")
            write(root, "README.md", "# Example\n")
            v3.build_pack(root, route_query="billing charge")
            pack = root / ".claude" / "project-context"

            self.assertTrue((pack / "QUERY_CONTEXT.md").exists())
            self.assertTrue((pack / "QUERY_RESULTS.json").exists())

            results = json.loads((pack / "QUERY_RESULTS.json").read_text(encoding="utf-8"))

        self.assertEqual("billing charge", results["query"])
        self.assertNotEqual([], results["ranked"])
        top_paths = [row["path"] for row in results["ranked"]]
        self.assertIn("src/billing/charge.py", top_paths)
        self.assertLess(top_paths.index("src/billing/charge.py"), 3)


class ImportGraphTests(unittest.TestCase):
    def test_import_graph_resolves_python_package_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "billing/__init__.py", "")
            write(root, "billing/charge.py", "def charge():\n    return 1\n")
            write(root, "app/main.py", "from billing.charge import charge\n\ncharge()\n")
            files = v3.walk_files(root)
            graph = v3.build_import_graph(root, files)

        self.assertIn("billing/charge.py", graph["imports_by_file"].get("app/main.py", []))
        self.assertIn("app/main.py", graph["reverse_imports"].get("billing/charge.py", []))


class TokenCountsTests(unittest.TestCase):
    def test_token_counts_sorted_descending_and_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "big.py", "x = 1\n" * 4000)
            write(root, "small.py", "x = 1\n")
            write(root, "mid.py", "x = 1\n" * 200)
            files = v3.walk_files(root)
            by_file, by_dir, token_map = v3.build_token_counts(root, files)

        self.assertLessEqual(len(by_file), v3.MAX_TOKEN_ROWS)
        counts = [count for _, count in by_file]
        self.assertEqual(counts, sorted(counts, reverse=True))
        top_path, _ = by_file[0]
        self.assertEqual("big.py", top_path)
        self.assertGreater(token_map["big.py"], token_map["small.py"])


if __name__ == "__main__":
    unittest.main()
