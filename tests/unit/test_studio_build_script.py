"""Exercise Studio build source selection without building Docker images."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

BUILD_SCRIPT = Path(__file__).resolve().parents[2] / "deploy/studio/build.sh"
PRIMARY = "https://primary.invalid/simple/"
FALLBACK = "https://fallback.invalid/simple/"
STAGES = ["base.Dockerfile", "bio.Dockerfile", "browser-office.Dockerfile"]
PIP_PROCESS_ERROR = (
    'ERROR: process "/bin/sh -c python -m pip install scanpy" '
    "did not complete successfully: exit code: 1"
)
HASH_FAILURE = "ERROR: THESE PACKAGES DO NOT MATCH THE HASHES\n" + PIP_PROCESS_ERROR


def run_build(
    tmp_path: Path,
    *,
    failed_stage: str = "",
    fallback: str | None = FALLBACK,
    fail_all: bool = False,
    failure_log: str = HASH_FAILURE,
) -> tuple[subprocess.CompletedProcess[str], list[list[str]]]:
    docker = tmp_path / "docker"
    calls_file = tmp_path / "docker-calls.jsonl"
    docker.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['STUDIO_TEST_CALLS'], 'a') as calls:\n"
        "    calls.write(json.dumps(args) + '\\n')\n"
        "stage = Path(args[args.index('-f') + 1]).name\n"
        "primary = 'PIP_INDEX_URL=' + os.environ['PIP_INDEX_URL'] in args\n"
        "failed = stage == os.environ['STUDIO_TEST_FAILED_STAGE']\n"
        "if failed and (primary or os.environ['STUDIO_TEST_FAIL_ALL']):\n"
        "    print(os.environ['STUDIO_TEST_FAILURE_LOG'], file=sys.stderr)\n"
        "    sys.exit(17)\n"
    )
    docker.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        "CYGNUSX_IMAGE_TAG": "test-9664dded",
        "PIP_INDEX_URL": PRIMARY,
        "PIP_TIMEOUT": "15",
        "PIP_RETRIES": "2",
        "STUDIO_TEST_CALLS": str(calls_file),
        "STUDIO_TEST_FAILED_STAGE": failed_stage,
        "STUDIO_TEST_FAIL_ALL": "1" if fail_all else "",
        "STUDIO_TEST_FAILURE_LOG": failure_log,
        "STUDIO_BUILD_LOG_DIR": str(tmp_path / "logs"),
    }
    if fallback is None:
        env.pop("PIP_FALLBACK_INDEX_URL", None)
    else:
        env["PIP_FALLBACK_INDEX_URL"] = fallback
    result = subprocess.run(
        ["bash", str(BUILD_SCRIPT)], env=env, capture_output=True, text=True, timeout=15
    )
    return result, [json.loads(line) for line in calls_file.read_text().splitlines()]


def stages(calls: list[list[str]]) -> list[str]:
    return [Path(args[args.index("-f") + 1]).name for args in calls]


def test_success_uses_one_index_for_all_images(tmp_path: Path) -> None:
    result, calls = run_build(tmp_path)
    assert result.returncode == 0, result.stderr
    assert stages(calls) == STAGES
    for args in calls:
        assert f"PIP_INDEX_URL={PRIMARY}" in args
        assert "PIP_TIMEOUT=15" in args
        assert "PIP_RETRIES=2" in args
    assert "切换" not in result.stderr


@pytest.mark.parametrize("failed_stage", STAGES)
def test_failure_stops_chain_then_retries_every_image(
    tmp_path: Path, failed_stage: str
) -> None:
    result, calls = run_build(tmp_path, failed_stage=failed_stage)
    assert result.returncode == 0, result.stderr
    first_attempt = STAGES[: STAGES.index(failed_stage) + 1]
    assert stages(calls) == first_attempt + STAGES
    assert all(f"PIP_INDEX_URL={PRIMARY}" in args for args in calls[: len(first_attempt)])
    assert all(f"PIP_INDEX_URL={FALLBACK}" in args for args in calls[len(first_attempt) :])
    assert "从 base 重试整条镜像链" in result.stderr
    assert "首个失败日志" in result.stderr
    assert len(list((tmp_path / "logs").glob("*.log"))) == len(calls)


@pytest.mark.parametrize("fallback", ["", PRIMARY])
def test_disabled_or_identical_fallback_preserves_failure(tmp_path: Path, fallback: str) -> None:
    result, calls = run_build(tmp_path, failed_stage="bio.Dockerfile", fallback=fallback)
    assert result.returncode == 17
    assert stages(calls) == STAGES[:2]
    assert "完成" not in result.stdout


def test_failed_fallback_is_not_reported_as_success(tmp_path: Path) -> None:
    result, calls = run_build(tmp_path, failed_stage="bio.Dockerfile", fail_all=True)
    assert result.returncode == 17
    assert stages(calls) == STAGES[:2] * 2
    assert "完成" not in result.stdout
    assert "备用源构建也失败" in result.stderr


@pytest.mark.parametrize(
    "failure_log",
    [
        "ERROR: Unknown frontend grpc server closed unexpectedly",
        'ERROR: process "/bin/sh -c apt-get update" did not complete: exit code: 100',
        "ERROR: No matching distribution found for incompatible-package\n" + PIP_PROCESS_ERROR,
        "chown: Permission denied\n" + PIP_PROCESS_ERROR,
    ],
)
def test_unrelated_failure_does_not_switch_index(tmp_path: Path, failure_log: str) -> None:
    result, calls = run_build(
        tmp_path, failed_stage="browser-office.Dockerfile", failure_log=failure_log
    )
    assert result.returncode == 17
    assert stages(calls) == STAGES
    assert all(f"PIP_INDEX_URL={PRIMARY}" in args for args in calls)
    assert "非 pip 下载/哈希错误" in result.stderr
    assert "从 base 重试" not in result.stderr
    logs = list((tmp_path / "logs").glob("*browser-office.*.log"))
    assert len(logs) == 1
    assert failure_log in logs[0].read_text()


@pytest.mark.parametrize("error", ["ReadTimeoutError", "SSLError"])
def test_pip_network_failure_can_retry(tmp_path: Path, error: str) -> None:
    result, calls = run_build(
        tmp_path, failed_stage="base.Dockerfile", failure_log=error + "\n" + PIP_PROCESS_ERROR
    )
    assert result.returncode == 0, result.stderr
    assert stages(calls) == STAGES[:1] + STAGES


def test_default_fallback_uses_tuna(tmp_path: Path) -> None:
    result, calls = run_build(tmp_path, failed_stage="bio.Dockerfile", fallback=None)
    assert result.returncode == 0, result.stderr
    assert all(
        "PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple/" in args for args in calls[2:]
    )
