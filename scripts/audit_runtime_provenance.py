"""Read-only Phase 0B provenance collector. Never prints secret configuration."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parents[1]


class _ComposeLoader(yaml.SafeLoader):
    """PyYAML lacks Compose's !reset/!override tags, which are valid in compose files."""


def _compose_tag(loader: yaml.SafeLoader, node: yaml.Node) -> object:
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    return loader.construct_scalar(node)


_ComposeLoader.add_constructor("!reset", _compose_tag)
_ComposeLoader.add_constructor("!override", _compose_tag)


def load_compose(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], yaml.load(path.read_text(encoding="utf-8"), Loader=_ComposeLoader))


def command(args: list[str], cwd: Path = ROOT) -> dict[str, Any]:
    try:
        result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=15)
        return {"exit_code": result.returncode, "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip()}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"exit_code": None, "stdout": "", "stderr": str(error)}


def digest(path: Path) -> str | None:
    if not path.is_file():
        return None
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def repository(path: Path, *, submodule: bool) -> dict[str, Any]:
    if not path.is_dir():
        return {"path": str(path), "status": "NOT TESTED", "reason": "path absent"}
    status = command(["git", "status", "--short"], path)
    remote = command(["git", "remote", "get-url", "origin"], path)["stdout"]
    remote = re.sub(r"(https?://)[^/@]+@", r"\1[redacted]@", remote)
    return {
        "path": str(path), "submodule": submodule,
        "branch": command(["git", "branch", "--show-current"], path)["stdout"],
        "head": command(["git", "rev-parse", "HEAD"], path)["stdout"],
        "remote": remote, "dirty": bool(status["stdout"]),
        "dirty_paths": status["stdout"].splitlines(),
        "status": "PASS" if status["exit_code"] == 0 else "BLOCKED",
        "deployed_head": None, "deployed_status": "BLOCKED",
    }


def collect() -> dict[str, Any]:
    from cygnusx.core.config import get_settings
    from cygnusx.tools.download.config import get_download_config

    repos = [repository(ROOT, submodule=False)]
    modules = command(["git", "submodule", "status", "--recursive"])
    for line in modules["stdout"].splitlines():
        fields = line.strip().split()
        if len(fields) >= 2:
            repos.append(repository(ROOT / fields[1], submodule=True))
    for name in ("polariseq", "EBIDownload", "bioreport", "Treasure-Seeking_Mouse"):
        repos.append(repository(ROOT.parent / name, submodule=False))

    compose_files = [ROOT / "deploy/docker/docker-compose.yml",
                     ROOT / "deploy/docker/docker-compose.worker.yml"]
    services = []
    for compose in compose_files:
        data = load_compose(compose)
        for name, service in data["services"].items():
            build = service.get("build")
            context = build.get("context") if isinstance(build, dict) else build
            services.append({
                "compose": str(compose.relative_to(ROOT)), "service": name,
                "configured_image_expression": service.get("image"),
                "expected_version": None,
                "configured_version": service.get("image"),
                "observed_runtime_version": None,
                "verification_status": "BLOCKED",
                "build": build,
                "resolved_build_context": str((compose.parent / context).resolve()) if context else None,
                "mount_expressions": service.get("volumes", []),
                "expose": service.get("expose", []), "ports": service.get("ports", []),
                "healthcheck": service.get("healthcheck"),
                "observed_image_id": None, "observed_digest": None,
                "observed_revision_label": None, "runtime_status": "BLOCKED",
            })
    inventory = yaml.safe_load((ROOT / "deploy/image-mapping.yaml").read_text())["images"]
    config = get_download_config()
    settings = get_settings()
    binary = Path(config.binaries.ebi or settings.ebi_download_binary)
    config_path = Path(config.binaries.ebi_config or settings.ebi_download_yaml)
    version = command([str(binary), "--version"]) if binary.exists() else None
    help_result = command([str(binary), "download", "--help"]) if binary.exists() else None
    help_text = help_result["stdout"] if help_result else ""
    flags = ["--accession", "--output", "--download", "--multithreads", "--aws-threads",
             "--yaml", "--log-format", "--progress-port", "--write-progress-key", "--dry-run"]
    docker = command(["docker", "version", "--format", "{{.Server.Version}}"])
    treasure = ROOT / "pipelines/Treasure-Seeking_Mouse"
    treasure_head = command(["git", "rev-parse", "HEAD"], treasure)["stdout"]
    worker = yaml.safe_load((ROOT / "data/worker_config.yaml").read_text())
    worker_pipeline_root = Path(worker["paths"]["pipeline_dir"])
    for name in ("RNAFlow", "ATACFlow"):
        repos.append(repository(worker_pipeline_root / name, submodule=False))
    flows = []
    for path in sorted((ROOT / "flows").glob("*.yaml")):
        data = yaml.safe_load(path.read_text())
        execution = data.get("execution", {})
        snakefile = execution.get("snakefile", "")
        host_snakefile = worker_pipeline_root / snakefile.removeprefix("/opt/cygnusx/pipelines/")
        flows.append({"path": str(path.relative_to(ROOT)), "sha256": digest(path),
                      "configured_host_snakefile": str(host_snakefile),
                      "host_snakefile_exists": host_snakefile.is_file(),
                      "host_snakefile_sha256": digest(host_snakefile),
                      "id": data.get("meta", {}).get("id"),
                      "version": data.get("meta", {}).get("version"),
                      "execution": data.get("execution"),
                      "expected_version": data.get("meta", {}).get("version"),
                      "configured_version": data.get("meta", {}).get("version"),
                      "observed_runtime_version": None, "verification_status": "BLOCKED"})
    return {
        "schema_version": 1, "generated_at": datetime.now(UTC).isoformat(),
        "scope": "local source and host audit; NOT deployment attestation",
        "repositories": repos, "services": services, "image_inventory": inventory,
        "docker": {"status": "BLOCKED" if docker["exit_code"] != 0 else "NOT TESTED",
                   "probe": docker, "reason": "No container attestation or execution performed"},
        "treasure": {"configured_default_revision": "1ea2f79", "source_head": treasure_head,
                     "drift_status": "FAIL" if not treasure_head.startswith("1ea2f79") else "PASS",
                     "image_id": None, "image_digest": None, "runtime_status": "BLOCKED"},
        "download_binary": {
            "configured_path": str(binary), "resolved_host_path": str(binary.resolve()),
            "host_exists": binary.exists(), "host_sha256": digest(binary),
            "host_executable": shutil.which(str(binary)) is not None,
            "host_version": version, "host_download_help": help_result,
            "expected_version": None, "configured_version": "external file: no pinned version",
            "observed_runtime_version": version["stdout"] if version else None,
            "verification_status": "PASS (host only); BLOCKED (Worker container)",
            "worker_required_flags": {flag: flag in help_text for flag in flags},
            "host_status": "PASS" if version and version["exit_code"] == 0 else "BLOCKED",
            "yaml_path": str(config_path), "yaml_exists": config_path.exists(),
            "yaml_sha256": digest(config_path), "yaml_contents": "NOT COLLECTED: may contain secrets",
            "configuration_precedence": "download_config.yaml binaries, derived STORAGE_PATH, then Settings fallback",
            "container_path": None, "container_sha256": None, "container_version": None,
            "container_status": "BLOCKED", "source_commit_binding": "NOT TESTED",
            "accessions": {
                "GSE": "NOT TESTED: no GEO expansion implementation found in either Rust source",
                "GSM": "NOT TESTED: no GEO expansion implementation found in either Rust source",
                "PRJNA": "Contract: ENA filereport accession forwarded; Runtime NOT TESTED",
                "SRR": "Contract: ENA filereport accession forwarded; Runtime NOT TESTED",
            },
        },
        "worker_paths": worker["paths"], "flows": flows, "workflow_runtimes": {
            "configured_worker_image": "cygnusx-worker:v0.0.2dev (default)",
            "conda_prefix_expression": "${STORAGE_PATH:-/data/cygnusx}/.conda_envs",
            "snakemake": command(["snakemake", "--version"]),
            "host_python": command(["python", "--version"]),
            "host_R": command(["R", "--version"]),
            "worker_python": None, "worker_R": None, "worker_snakemake": None,
            "reference_mount_status": "BLOCKED", "output_permission_status": "BLOCKED",
            "verification_status": "BLOCKED: host tools do not attest Worker runtime",
        },
        "redis": {"server_binary": shutil.which("redis-server"), "runtime_status": "BLOCKED",
                  "reason": "No isolated Redis; configured Redis intentionally not contacted"},
        "blockers": ["Treasure source/default tag drift", "No image digest/revision attestation",
                     "No real Redis multiworker CAS run", "MCP external transports not accepted",
                     "No live Worker binary/mount verification"],
        "readiness": "BLOCKED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true", help="exit 2 while runtime gates are unresolved")
    args = parser.parse_args()
    manifest = collect()
    content = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
    return 2 if args.strict and manifest["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
