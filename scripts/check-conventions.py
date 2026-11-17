#!/usr/bin/env python3
"""Comparer les conventions locales de deux dépôts, sans réseau ni daemon.

Seuls les fichiers publics de structure, Renovate et CI sont lus. Aucun .env,
certificat, secret ou fichier de données n'est ouvert. Aucun fichier n'est modifié.
"""

import argparse
import json
from pathlib import Path
import sys

import yaml


def read_config(root, relative):
    text = (root / relative).read_text()
    config = json.loads(text) if relative.endswith(".json") else yaml.safe_load(text)
    if not isinstance(config, dict):
        raise ValueError(f"{relative} doit être un mapping")
    return config


def compare(repository, reference):
    errors = []
    for relative in ("renovate.json", ".gitlab/renovate.gitlab-ci.yml"):
        if read_config(repository, relative) != read_config(reference, relative):
            errors.append(f"{relative} : différent du socle de référence")
    ci = read_config(repository, ".gitlab-ci.yml")
    reference_ci = read_config(reference, ".gitlab-ci.yml")
    for key in ("stages", "workflow"):
        if ci.get(key) != reference_ci.get(key):
            errors.append(f".gitlab-ci.yml : {key} différent du socle de référence")
    for include in reference_ci.get("include", []):
        if include not in ci.get("include", []):
            errors.append(".gitlab-ci.yml : include du socle manquant")
    # Les autres includes/jobs propres aux applications restent autorisés.
    for relative in ("README.md", "RENOVATE.md", ".gitignore"):
        if not (repository / relative).is_file():
            errors.append(f"{relative} : absent")
    stacks = sorted(repository.glob("*/compose.yaml"))
    if (repository / "compose.yaml").is_file():
        stacks.append(repository / "compose.yaml")
    if not stacks:
        errors.append("Aucune stack compose.yaml à la racine ou dans un sous-dossier")
    for stack in stacks:
        for relative in ("README.md", "example.env"):
            # Conserver aussi la convention .env.example lorsqu'elle est déjà adoptée.
            if relative == "example.env" and (stack.parent / ".env.example").is_file():
                continue
            if not (stack.parent / relative).is_file():
                errors.append(f"{stack.parent.relative_to(repository)}/{relative} : absent")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True, help="Dépôt local de référence")
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        errors = compare(args.repository.resolve(), args.reference.resolve())
    except (OSError, ValueError, yaml.YAMLError) as error:
        print(f"Contrôle impossible : {type(error).__name__}", file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print(f"ÉCART : {error}")
        return 1
    print("OK : structure cible valide ; règles Renovate et socle CI identiques à la référence ; extensions applicatives autorisées.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
