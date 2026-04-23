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

    def test_honors_simple_gitignore_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".gitignore").write_text("ignored.log\nignored-dir/\n", encoding="utf-8")
            (root / "ignored.log").write_text("skip\n", encoding="utf-8")
            (root / "keep.log").write_text("keep\n", encoding="utf-8")
            ignored_dir = root / "ignored-dir"
            ignored_dir.mkdir()
            (ignored_dir / "file.txt").write_text("skip\n", encoding="utf-8")

            paths = {file_info.path for file_info in build_context_pack.walk_files(root)}

        self.assertIn("keep.log", paths)
        self.assertNotIn("ignored.log", paths)
        self.assertNotIn("ignored-dir/file.txt", paths)


class DetectionTests(unittest.TestCase):
    def test_detect_stack_infers_python_from_python_files_without_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = [
                build_context_pack.FileInfo(
                    path="scripts/tool.py",
                    ext=".py",
                    size=12,
                    top_level="scripts",
                )
            ]

            stack = build_context_pack.detect_stack(root, files)

        self.assertIn("Python", stack["runtime"])
        self.assertIn("Python scripts", stack["tooling"])

    def test_build_areas_labels_scripts_as_tooling(self):
        files = [
            build_context_pack.FileInfo(
                path="scripts/build_context_pack.py",
                ext=".py",
                size=100,
                top_level="scripts",
            )
        ]

        areas = build_context_pack.build_areas(files)

        self.assertEqual("tooling or automation", areas["scripts"]["inferred_role"])


if __name__ == "__main__":
    unittest.main()
