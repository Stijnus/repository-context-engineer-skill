import tempfile
import unittest
from pathlib import Path

from scripts import build_context_pack


class WalkFilesTests(unittest.TestCase):
    def test_excludes_generated_project_context_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Example\n", encoding="utf-8")
            generated = root / ".claude" / "project-context"
            generated.mkdir(parents=True)
            (generated / "OVERVIEW.md").write_text("# Generated\n", encoding="utf-8")

            paths = {file_info.path for file_info in build_context_pack.walk_files(root)}

        self.assertIn("README.md", paths)
        self.assertNotIn(".claude/project-context/OVERVIEW.md", paths)


if __name__ == "__main__":
    unittest.main()
