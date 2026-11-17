"""Validation locale : aucun daemon, secret ou fichier .env réel n'est lu."""

import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
BASELINE = "03ad6be4a667d1d7ad8a98626fa1c5d58348483e"
STACKS = {path.parent.name: yaml.safe_load(path.read_text())
          for path in sorted(ROOT.glob("*/compose.yaml"))}
VOLUME_VARIABLES = {
    "arr": {"prowlarr-config": "PROWLARR_CONFIG_VOLUME"},
    "jellyfin": {"jellyfin-config": "JELLYFIN_CONFIG_VOLUME", "jellyfin-cache": "JELLYFIN_CACHE_VOLUME"},
    "seerr": {"seerr-config": "SEERR_CONFIG_VOLUME"},
    "torrents": {},
    "tracearr": {"tracearr-backups": "TRACEARR_BACKUPS_VOLUME", "tracearr-images": "TRACEARR_IMAGES_VOLUME",
                 "timescale-data": "TIMESCALE_DATA_VOLUME", "redis-data": "REDIS_DATA_VOLUME"},
}


def original(stack):
    return subprocess.check_output(
        ["git", "show", f"{BASELINE}:{stack}/compose.yaml"], cwd=ROOT, text=True,
    )


def source_variable(source):
    return source[2:].split(":", 1)[0].rstrip("}") if source.startswith("${") else source


def mounts(service):
    result = {}
    for mount in service["volumes"]:
        if isinstance(mount, str):
            source, target = mount.split(":")
            kind, writable = "volume", True
        else:
            source, target = mount["source"], mount["target"]
            kind, writable = mount["type"], not mount.get("read_only", False)
        result[target] = (kind, source_variable(source), writable)
    return result


def environment(service):
    value = service.get("environment", {})
    return dict(item.split("=", 1) for item in value) if isinstance(value, list) else value


class StackTests(unittest.TestCase):
    def test_inventory_identity_environment_gpu_and_mounts_preserved(self):
        self.assertEqual(set(STACKS), set(VOLUME_VARIABLES))
        for stack, config in STACKS.items():
            before = yaml.safe_load(original(stack))
            self.assertEqual(config["name"], before["name"])
            self.assertEqual(set(config["services"]), set(before["services"]))
            for name, service in config["services"].items():
                old = before["services"][name]
                with self.subTest(stack=stack, service=name):
                    # Les images evoluent via Renovate ; seuls les invariants de donnees sont figes.
                    for key in ("user", "runtime", "deploy"):
                        self.assertEqual(service.get(key), old.get(key))
                    self.assertEqual(environment(service), environment(old))
                    self.assertEqual(mounts(service), mounts(old))
                    self.assertNotIn("container_name", service)

    def test_write_access_is_explicit_for_every_existing_mount(self):
        for stack in STACKS.values():
            for service in stack["services"].values():
                self.assertFalse(service.get("read_only", False))
                for mount in service["volumes"]:
                    self.assertIsInstance(mount, dict)
                    self.assertIs(mount["read_only"], False)
                    if mount["type"] == "bind":
                        self.assertIs(mount["bind"]["create_host_path"], False)
                        self.assertIn(":?", mount["source"])

    def test_existing_named_volumes_are_external_and_names_required(self):
        for name, stack in STACKS.items():
            self.assertEqual(set(stack.get("volumes", {})), set(VOLUME_VARIABLES[name]))
            for key, variable in VOLUME_VARIABLES[name].items():
                volume = stack["volumes"][key]
                self.assertIs(volume["external"], True)
                self.assertTrue(volume["name"].startswith("${" + variable + ":?"))

    def test_runtime_security_and_bounded_logs(self):
        for stack in STACKS.values():
            for service in stack["services"].values():
                self.assertEqual(service["restart"], "unless-stopped")
                self.assertIn("no-new-privileges:true", service["security_opt"])
                self.assertEqual(service["logging"], {
                    "driver": "local", "options": {"max-size": "10m", "max-file": "3"},
                })
                for forbidden in ("privileged", "network_mode", "pid", "ipc", "env_file"):
                    self.assertNotIn(forbidden, service)

    def test_tls_pki_routing_and_host_port_scope(self):
        for stack in STACKS.values():
            self.assertEqual(stack["networks"]["traefik"], {
                "name": "${TRAEFIK_NETWORK:-traefik-net}", "external": True,
            })
            for name, service in stack["services"].items():
                if name == "qbittorrent":
                    self.assertEqual(len(service["ports"]), 2)
                    for port in service["ports"]:
                        self.assertTrue(port.startswith("${TORRENT_BIND_IP:?"))
                        self.assertRegex(port, r"\}:6881:6881/(tcp|udp)$")
                else:
                    self.assertNotIn("ports", service)
                if "traefik" in service["networks"]:
                    labels = service["labels"]
                    prefix = f"traefik.http.routers.{name}."
                    self.assertEqual(labels["traefik.enable"], "true")
                    self.assertEqual(labels["traefik.docker.network"], "${TRAEFIK_NETWORK:-traefik-net}")
                    self.assertEqual(labels[prefix + "entrypoints"], "${TRAEFIK_ENTRYPOINT:-websecure}")
                    self.assertEqual(labels[prefix + "tls"], "true")
                    self.assertEqual(labels[prefix + "tls.certresolver"], "${TRAEFIK_CERTRESOLVER:-pki}")
                    self.assertIn(":?", labels[prefix + "rule"])

    def test_databases_private_and_health_dependencies_preserved(self):
        stack = STACKS["tracearr"]
        self.assertIs(stack["networks"]["backend"]["internal"], True)
        for name in ("timescale", "redis"):
            service = stack["services"][name]
            self.assertEqual(service["networks"], ["backend"])
            self.assertNotIn("labels", service)
            self.assertEqual(stack["services"]["tracearr"]["depends_on"][name], {"condition": "service_healthy"})
            self.assertIsInstance(service["command"], list)

    def test_environment_examples_complete_and_images_pinned(self):
        for name, stack in STACKS.items():
            compose = (ROOT / name / "compose.yaml").read_text()
            example = (ROOT / name / "example.env").read_text()
            self.assertEqual(set(re.findall(r"\$\{([A-Z_]+)", compose)),
                             set(re.findall(r"^([A-Z_]+)=", example, re.M)))
            for service in stack["services"].values():
                self.assertRegex(service["image"], r":[^@]+@sha256:[0-9a-f]{64}$")
                self.assertNotIn(":latest", service["image"])

    def test_jellyfin_healthcheck_does_not_bypass_tls(self):
        test = STACKS["jellyfin"]["services"]["jellyfin"]["healthcheck"]["test"]
        self.assertEqual(test[:2], ["CMD", "curl"])
        self.assertIn("http://localhost:8096/health", test)
        self.assertNotIn("-k", test)
        self.assertNotIn("--insecure", test)


class ComposeCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        binary = os.environ.get("COMPOSE_BIN") or shutil.which("docker-compose")
        if not binary:
            raise unittest.SkipTest("CLI Compose absent ; définir COMPOSE_BIN pour le rendu statique")
        cls.cli = shlex.split(binary)

    def test_render_preserves_physical_mounts_and_rejects_missing_required_values(self):
        temp_root = "/tmp/opencode" if Path("/tmp/opencode").is_dir() else None
        with tempfile.TemporaryDirectory(prefix="media-stack-tests-", dir=temp_root) as temp:
            temp = Path(temp)
            env = {"PATH": os.environ["PATH"], "HOME": str(temp)}
            for name, stack in STACKS.items():
                values = {}
                for line in (ROOT / name / "example.env").read_text().splitlines():
                    if line and not line.startswith("#"):
                        key, value = line.split("=", 1)
                        values[key] = value or "a" * 64
                values.update({variable: f"{name}_{key}" for key, variable in VOLUME_VARIABLES[name].items()})
                if "TRUST_PROXY" in values:
                    values["TRUST_PROXY"] = "192.0.2.1/32"
                if "TORRENT_BIND_IP" in values:
                    values["TORRENT_BIND_IP"] = "192.0.2.2"
                envfile = temp / f"{name}.env"
                def write_env(exclude=None):
                    envfile.write_text("".join(f"{k}={v}\n" for k, v in values.items() if k != exclude))
                    envfile.chmod(0o600)
                write_env()
                base = [*self.cli, "--env-file", str(envfile), "-p", name]
                command = [*base, "-f", str(ROOT / name / "compose.yaml"), "config"]
                subprocess.run([*command, "--quiet"], env=env, check=True, capture_output=True, timeout=30)
                actual = json.loads(subprocess.check_output([*command, "--format", "json"], env=env, timeout=30))
                before_file = temp / f"{name}-before.yaml"
                before_file.write_text(original(name))
                before = json.loads(subprocess.check_output(
                    [*base, "-f", str(before_file), "config", "--format", "json"], env=env, timeout=30,
                ))
                for service in actual["services"]:
                    def physical_mounts(config):
                        result = []
                        for mount in config["services"][service]["volumes"]:
                            mount = dict(mount)
                            if mount["type"] == "volume":
                                mount["source"] = config["volumes"][mount["source"]]["name"]
                                # Forme courte : Compose émet volume:{} ; forme longue : absent.
                                mount.setdefault("volume", {})
                            # L'absence de read_only équivaut à false en Compose.
                            mount["read_only"] = mount.get("read_only", False)
                            result.append(mount)
                        return result
                    self.assertEqual(physical_mounts(actual), physical_mounts(before))
                    for key in ("user", "environment", "runtime", "deploy", "command"):
                        self.assertEqual(actual["services"][service].get(key), before["services"][service].get(key))
                for variable in set(re.findall(r"\$\{([A-Z_]+):\?", (ROOT / name / "compose.yaml").read_text())):
                    with self.subTest(stack=name, missing=variable):
                        write_env(exclude=variable)
                        result = subprocess.run([*command, "--quiet"], env=env, capture_output=True, timeout=30)
                        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
