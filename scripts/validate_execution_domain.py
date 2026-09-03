#!/usr/bin/env python3
"""Static dependency boundary validator for the PAPER/SHADOW execution domain."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_SCHEMA = "smial.execution-domain.v1"
EXPECTED_DOMAIN_ID = "FACTORY_PAPER_SHADOW_EXECUTION_V1"
FACTORY_PREFIX = "solana_alpha_lab.factory."


class ExecutionDomainError(ValueError):
    """Fail-closed execution-domain contract error."""


def posix(path: str | Path) -> str:
    return Path(path).as_posix()


def normalize_repo_relative(path: str) -> str:
    candidate = posix(path)
    if candidate.startswith("/") or candidate.startswith("\\"):
        raise ExecutionDomainError(f"ABSOLUTE_PATH_FORBIDDEN:{candidate}")
    parts = Path(candidate).parts
    if ".." in parts:
        raise ExecutionDomainError(f"PARENT_TRAVERSAL_FORBIDDEN:{candidate}")
    return candidate


def source_path_to_module(path: str) -> str:
    rel = normalize_repo_relative(path)
    if not rel.startswith("src/") or not rel.endswith(".py"):
        raise ExecutionDomainError(f"SOURCE_PATH_INVALID:{rel}")
    return rel[4:-3].replace("/", ".")


def load_execution_domain(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ExecutionDomainError("MANIFEST_NOT_OBJECT")
    return document


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=posix(path))


def factory_imports(path: Path | str, *, root: Path) -> set[str]:
    rel = normalize_repo_relative(str(path))
    source = root / rel
    if not source.is_file():
        raise ExecutionDomainError(f"SOURCE_MISSING:{posix(path)}")
    package = source_path_to_module(rel).rsplit(".", 1)[0]
    tree = _parse(source)
    found: set[str] = set()

    def _maybe_add(absolute: str) -> None:
        if absolute == "solana_alpha_lab.factory" or absolute.startswith(FACTORY_PREFIX):
            found.add(absolute)

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                base_parts = package.split(".")
                up = node.level - 1
                if up > len(base_parts):
                    raise ExecutionDomainError(f"RELATIVE_IMPORT_ESCAPE:{rel}")
                parent = ".".join(base_parts[: len(base_parts) - up])
                if node.module:
                    absolute = f"{parent}.{node.module}" if parent else node.module
                    _maybe_add(absolute)
                else:
                    for alias in node.names:
                        absolute = f"{parent}.{alias.name}" if parent else alias.name
                        _maybe_add(absolute)
                continue
            if node.module and node.module.startswith(FACTORY_PREFIX.rstrip(".")):
                found.add(node.module)
            elif node.module and node.module == "solana_alpha_lab.factory":
                found.add("solana_alpha_lab.factory")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name == "solana_alpha_lab.factory" or name.startswith(FACTORY_PREFIX):
                    found.add(name)
    return found


def direct_test_importers(source_modules: set[str], *, root: Path) -> set[str]:
    module_names = {source_path_to_module(path) for path in source_modules}
    tests_root = root / "tests"
    importers: set[str] = set()
    for test_path in sorted(tests_root.glob("test_*.py")):
        rel = test_path.relative_to(root).as_posix()
        tree = _parse(test_path)
        imports_factory_execution = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module in module_names:
                    imports_factory_execution = True
                    break
            elif isinstance(node, ast.Import):
                if any(alias.name in module_names for alias in node.names):
                    imports_factory_execution = True
                    break
        if imports_factory_execution:
            importers.add(rel)
    return importers


def _require_unique_paths(label: str, paths: list[str]) -> list[str]:
    normalized = [normalize_repo_relative(path) for path in paths]
    seen: set[str] = set()
    duplicates: set[str] = set()
    for path in normalized:
        if path in seen:
            duplicates.add(path)
        seen.add(path)
    if duplicates:
        raise ExecutionDomainError(
            f"{label}_DUPLICATE:" + ",".join(sorted(duplicates)[:20])
        )
    return normalized


def validate_execution_domain(
    manifest: Mapping[str, Any], *, root: Path
) -> dict[str, Any]:
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ExecutionDomainError("MANIFEST_SCHEMA_INVALID")
    if manifest.get("domain_id") != EXPECTED_DOMAIN_ID:
        raise ExecutionDomainError("DOMAIN_ID_INVALID")
    if manifest.get("live_authority") is not False:
        raise ExecutionDomainError("LIVE_AUTHORITY_MUST_BE_FALSE")

    contract_paths = _require_unique_paths(
        "CONTRACT", list(manifest.get("contract_paths") or [])
    )
    adapter_consumers = _require_unique_paths(
        "ADAPTER", list(manifest.get("adapter_consumers") or [])
    )
    fast_modules = _require_unique_paths(
        "FAST_TEST", list(manifest.get("required_fast_test_modules") or [])
    )
    if not fast_modules:
        raise ExecutionDomainError("FAST_TEST_MODULES_EMPTY")

    raw_sources = manifest.get("source_modules")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise ExecutionDomainError("SOURCE_MODULES_MISSING")
    source_paths: list[str] = []
    allowed_by_source: dict[str, set[str]] = {}
    for row in raw_sources:
        if not isinstance(row, dict):
            raise ExecutionDomainError("SOURCE_MODULE_ROW_INVALID")
        path = normalize_repo_relative(str(row.get("path", "")))
        allowed = {
            str(item)
            for item in (row.get("allowed_factory_imports") or [])
            if str(item).strip()
        }
        for item in allowed:
            if not item.startswith("solana_alpha_lab.factory."):
                raise ExecutionDomainError(f"ALLOWED_IMPORT_NOT_FACTORY:{item}")
        source_paths.append(path)
        allowed_by_source[path] = allowed
    source_paths = _require_unique_paths("SOURCE", source_paths)

    for path in contract_paths + adapter_consumers + fast_modules + source_paths:
        if not (root / path).is_file():
            raise ExecutionDomainError(f"PATH_MISSING:{path}")

    import_edges: dict[str, list[str]] = {}
    for path in source_paths:
        actual = factory_imports(path, root=root)
        allowed = allowed_by_source[path]
        undeclared = sorted(actual - allowed)
        if undeclared:
            raise ExecutionDomainError(
                f"UNDECLARED_FACTORY_IMPORT:{path}:"
                + ",".join(undeclared[:20])
            )
        missing_allowed = sorted(allowed - actual)
        if missing_allowed:
            raise ExecutionDomainError(
                f"ALLOWED_IMPORT_NOT_PRESENT:{path}:"
                + ",".join(missing_allowed[:20])
            )
        import_edges[path] = sorted(actual)

    importers = direct_test_importers(set(source_paths), root=root)
    undeclared_importers = sorted(importers - set(fast_modules))
    if undeclared_importers:
        raise ExecutionDomainError(
            "UNDECLARED_EXECUTION_TEST_IMPORTER:"
            + ",".join(undeclared_importers[:20])
        )

    return {
        "domain_id": EXPECTED_DOMAIN_ID,
        "contract_paths": contract_paths,
        "source_modules": source_paths,
        "adapter_consumers": adapter_consumers,
        "required_fast_test_modules": fast_modules,
        "import_edges": import_edges,
        "direct_test_importers": sorted(importers),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "configs/execution_domain_v1.json",
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        manifest = load_execution_domain(args.manifest)
        validate_execution_domain(manifest, root=args.root)
    except ExecutionDomainError as exc:
        print(f"EXECUTION_DOMAIN_BOUNDARY: FAIL {exc}", file=sys.stderr)
        return 2
    print("EXECUTION_DOMAIN_BOUNDARY: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
