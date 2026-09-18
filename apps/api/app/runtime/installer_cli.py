from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from app.runtime.modules import MODULE_MANIFESTS, resolve_runtime_modules


def module_catalog() -> list[dict[str, object]]:
    return [asdict(manifest) for manifest in MODULE_MANIFESTS]


def resolved_module_keys(raw: str) -> list[str]:
    return [manifest.key for manifest in resolve_runtime_modules(raw)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Construction OS installer runtime manifest")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("catalog")
    resolve_parser = subparsers.add_parser("resolve")
    resolve_parser.add_argument("modules")

    args = parser.parse_args()
    if args.command == "catalog":
        print(json.dumps(module_catalog()))
        return
    if args.command == "resolve":
        print(json.dumps(resolved_module_keys(args.modules)))


if __name__ == "__main__":
    main()
