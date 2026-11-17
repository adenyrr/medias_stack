"""Garde-fous locaux de la configuration CI/Renovate, sans connexion GitLab."""

import json
from pathlib import Path
import re
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "renovate.json").read_text())
CI = yaml.safe_load((ROOT / ".gitlab/renovate.gitlab-ci.yml").read_text())
TEST_CI = yaml.safe_load((ROOT / ".gitlab/tests.gitlab-ci.yml").read_text())


class RenovateTests(unittest.TestCase):
    def test_pins_and_ci_required(self):
        self.assertIs(CONFIG["pinDigests"], True)
        self.assertIs(CONFIG["ignoreTests"], False)
        self.assertIs(CONFIG["platformAutomerge"], False)
        self.assertIs(CONFIG["automerge"], False)
        self.assertEqual(CONFIG["automergeType"], "pr")
        self.assertIn("docker-compose", CONFIG["enabledManagers"])
        self.assertIn("gitlabci", CONFIG["enabledManagers"])

    def test_update_rule_guards(self):
        rules = CONFIG["packageRules"]
        stable = next(rule for rule in rules if rule.get("automerge") is True)
        self.assertEqual(set(stable["matchUpdateTypes"]), {"minor", "patch", "digest"})
        manual = next(rule for rule in rules if "major" in rule.get("matchUpdateTypes", []))
        self.assertIs(manual["automerge"], False)
        self.assertTrue({"pin", "pinDigest", "replacement"}.issubset(manual["matchUpdateTypes"]))
        floating = next(rule for rule in rules if "matchCurrentValue" in rule)
        self.assertIs(floating["automerge"], False)
        self.assertGreater(rules.index(floating), rules.index(stable))
        pattern = floating["matchCurrentValue"]
        self.assertTrue(pattern.startswith("!/") and pattern.endswith("/"))
        complete_tag = re.compile(pattern[2:-1])
        for value in ("12.3", "latest", "pg18.4-ts2.29.1", "2.6.5.5623-ls165", "5.3.0_v2.1.2-ls484"):
            self.assertIsNone(complete_tag.fullmatch(value))
        for value in ("v3.5.1", "3.1.1", "8.10.2-alpine"):
            self.assertIsNotNone(complete_tag.fullmatch(value))

    def test_ci_bot_protected_and_after_validation(self):
        root = yaml.safe_load((ROOT / ".gitlab-ci.yml").read_text())
        self.assertEqual(root["include"], [
            {"local": "/.gitlab/renovate.gitlab-ci.yml"},
            {"local": "/.gitlab/tests.gitlab-ci.yml"},
        ])
        self.assertNotIn("stack-tests", CI)
        self.assertLess(root["stages"].index("validate"), root["stages"].index("renovate"))
        bot = CI["renovate"]
        self.assertEqual(bot["stage"], "renovate")
        self.assertEqual(bot["rules"][-1], {"when": "never"})
        for rule in bot["rules"][:-1]:
            self.assertIn('$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH', rule["if"])
            self.assertIn('$CI_COMMIT_REF_PROTECTED == "true"', rule["if"])
            self.assertTrue('"schedule"' in rule["if"] or '"web"' in rule["if"])
        self.assertEqual(bot["rules"][1]["when"], "manual")
        self.assertNotIn("needs", bot)
        self.assertFalse(bot.get("allow_failure", False))
        self.assertIn("NODE_EXTRA_CA_CERTS", bot["script"][0])
        self.assertIn("GIT_SSL_CAINFO", bot["script"][0])

    def test_validation_jobs_run_in_merge_request_pipelines(self):
        for name in ("compose-image-policy", "renovate-config-check", "stack-tests"):
            job = ({**CI, **TEST_CI})[name]
            self.assertEqual(job["stage"], "validate")
            self.assertEqual(job["rules"], [{"when": "on_success"}])
            self.assertFalse(job.get("allow_failure", False))
            image = job["image"]
            image = image["name"] if isinstance(image, dict) else image
            self.assertRegex(image, r":[^@]+@sha256:[0-9a-f]{64}$")
        self.assertIn("renovate-config-validator --strict renovate.json", CI["renovate-config-check"]["script"])

    def test_common_postgresql_and_hermes_exceptions_present(self):
        postgres = next(rule for rule in CONFIG["packageRules"]
                        if "postgres" in rule.get("matchPackageNames", []))
        self.assertIs(postgres["automerge"], True)
        self.assertEqual(set(postgres["matchUpdateTypes"]), {"minor", "patch", "digest"})
        hermes = next(rule for rule in CONFIG["packageRules"]
                      if "nousresearch/hermes-agent" in rule.get("matchPackageNames", []))
        self.assertIs(hermes["automerge"], False)

    def test_regex_managers_preserve_version_and_digest(self):
        digest = "sha256:" + "a" * 64
        samples = [
            "image: ${APP_IMAGE:-ghcr.io/example/app:1.2.3@" + digest + "}",
            "x-app-image: &app-image ghcr.io/example/app:1.2.3@" + digest,
        ]
        for manager, sample in zip(CONFIG["customManagers"], samples):
            # Traduction des seuls groupes nommés JS pour vérifier ces fixtures en Python.
            expression = re.sub(r"\(\?<([A-Za-z]+)>", r"(?P<\1>", manager["matchStrings"][0])
            match = re.search(expression, sample)
            self.assertIsNotNone(match)
            self.assertEqual(match["depName"], "ghcr.io/example/app")
            self.assertEqual(match["currentValue"], "1.2.3")
            self.assertEqual(match["currentDigest"], digest)


if __name__ == "__main__":
    unittest.main()
