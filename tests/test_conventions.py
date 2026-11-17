"""Tests du comparateur avec des dépôts factices, sans accès aux autres stacks."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import yaml


SPEC = importlib.util.spec_from_file_location(
    "conventions", Path(__file__).resolve().parents[1] / "scripts/check-conventions.py",
)
conventions = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(conventions)


class ConventionTests(unittest.TestCase):
    def setUp(self):
        root = "/tmp/opencode" if Path("/tmp/opencode").is_dir() else None
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.temp.cleanup)
        self.repository = Path(self.temp.name) / "repository"
        self.reference = Path(self.temp.name) / "reference"
        for repository in (self.repository, self.reference):
            (repository / ".gitlab").mkdir(parents=True)
            (repository / "renovate.json").write_text('{"pinDigests": true}')
            (repository / ".gitlab/renovate.gitlab-ci.yml").write_text("renovate: {stage: renovate}\n")
            (repository / ".gitlab-ci.yml").write_text(yaml.safe_dump({
                "include": [{"local": "/.gitlab/renovate.gitlab-ci.yml"}],
                "stages": ["validate", "renovate"], "workflow": {"rules": [{"when": "always"}]},
            }))
            for relative in ("README.md", "RENOVATE.md", ".gitignore", "example.env"):
                (repository / relative).write_text("")
            (repository / "compose.yaml").write_text("name: test\nservices: {}\n")

    def test_identical_configs_ignore_json_and_yaml_formatting(self):
        (self.repository / "renovate.json").write_text(json.dumps({"pinDigests": True}, indent=4))
        self.assertEqual(conventions.compare(self.repository, self.reference), [])

    def test_application_ci_extension_allowed(self):
        path = self.repository / ".gitlab-ci.yml"
        ci = yaml.safe_load(path.read_text())
        ci["include"].append({"local": "/.gitlab/tests.gitlab-ci.yml"})
        path.write_text(yaml.safe_dump(ci))
        self.assertEqual(conventions.compare(self.repository, self.reference), [])

    def test_renovate_policy_drift_rejected(self):
        (self.repository / "renovate.json").write_text('{"pinDigests": false}')
        self.assertTrue(any("renovate.json" in error for error in conventions.compare(self.repository, self.reference)))

    def test_ci_drift_and_missing_structure_rejected(self):
        (self.repository / ".gitlab/renovate.gitlab-ci.yml").write_text("renovate: {stage: validate}\n")
        (self.repository / "example.env").unlink()
        errors = conventions.compare(self.repository, self.reference)
        self.assertTrue(any("socle" in error for error in errors))
        self.assertTrue(any("example.env" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
