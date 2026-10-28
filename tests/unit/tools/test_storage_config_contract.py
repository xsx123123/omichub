"""仓库默认配置须随部署数据根变化，且 nginx 挂载必须与 alias 对齐。"""

import re
from pathlib import Path

import pytest
import yaml

from cygnusx.core.config import Settings
from cygnusx.infrastructure.config.storage_config import get_storage_config
from cygnusx.tools.download.config import DownloadConfigManager
from cygnusx.tools.fastq_qc.config import FastqQcConfigManager
from cygnusx.tools.terminal.config import TerminalConfigManager

pytestmark = pytest.mark.unit


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


@pytest.mark.parametrize("root", ["/data/omichub", "/srv/deployment-data"])
def test_repository_tool_configs_follow_settings(
    root: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(
        _env_file=None,
        storage_path=root,
        ebi_download_binary="",
        ebi_download_yaml="",
        cloud_ossutil_binary="",
        cloud_tosutil_binary="",
        cloud_obsutil_binary="",
    )
    for name in (
        "cygnusx.tools.download.config",
        "cygnusx.tools.fastq_qc.config",
        "cygnusx.tools.terminal.config",
        "cygnusx.infrastructure.config.storage_config",
    ):
        monkeypatch.setattr(name + ".get_settings", lambda: settings)
    assert get_storage_config().data_root == root
    terminal = TerminalConfigManager("tool_configs/terminal/terminal_config.yaml").get_config()
    assert terminal.storage.workspace_base == f"{root}/users"
    qc = FastqQcConfigManager("tool_configs/fastq_qc/config.yaml").get_config()
    assert qc.storage.root == f"{root}/qc/tasks"
    downloads = DownloadConfigManager("tool_configs/download/download_config.yaml").get_config()
    for key, filename in {
        "ebi": "EBIDownload",
        "ebi_config": "EBIDownload.yaml",
        "ossutil": "ossutil",
        "tosutil": "tosutil",
        "obsutil": "obsutil",
    }.items():
        assert getattr(downloads.binaries, key) == f"{root}/bin/{filename}"


def test_download_env_binary_override_is_honored(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        _env_file=None, storage_path="/srv/data", ebi_download_binary="/opt/EBIDownload"
    )
    monkeypatch.setattr("cygnusx.tools.download.config.get_settings", lambda: settings)
    config = DownloadConfigManager("tool_configs/download/download_config.yaml").get_config()
    assert config.binaries.ebi == "/opt/EBIDownload"


@pytest.mark.parametrize(
    ("compose_name", "nginx_name"),
    [
        ("docker-compose.yml", "nginx.conf"),
        ("docker-compose.prod.yml", "nginx.prod.conf"),
    ],
)
def test_nginx_tracks_alias_matches_readonly_data_volume(
    compose_name: str, nginx_name: str
) -> None:
    base = Path("deploy/docker")
    compose = yaml.load(
        (base / compose_name).read_text(encoding="utf-8"), Loader=_ComposeLoader
    )
    config = (base / "nginx" / nginx_name).read_text(encoding="utf-8")
    match = re.search(r"location\s+\^~\s+/tracks/\s*\{\s*alias\s+([^;]+);", config)
    assert match is not None
    target = match.group(1).rstrip("/")
    expected = "${CYGNUSX_DATA_ROOT:-/data/cygnusx}:" + target + ":ro"
    assert expected in compose["services"]["nginx"]["volumes"]


def test_legacy_phylo_compose_uses_the_configured_data_roots() -> None:
    compose = yaml.safe_load(Path("deploy/docker/docker-compose.phylo.yml").read_text())
    for service_name in ("phylo-worker", "phylo-worker-highmem"):
        service = compose["services"][service_name]
        assert (
            "${CYGNUSX_DATA_ROOT:-/data/cygnusx}:${STORAGE_PATH:-/data/cygnusx}:rw"
            in service["volumes"]
        )
        assert "STORAGE_PATH=${STORAGE_PATH:-/data/cygnusx}" in service["environment"]
