import pathlib

import yaml
from click.testing import CliRunner

from libvcs.sync.git import GitSync
from vcspull.cli import cli


def test_sync_cli_non_existent(tmp_path: pathlib.Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(cli, ["sync", "hi"])
        assert result.exit_code == 0
        assert "" in result.output


def test_sync(
    home_path: pathlib.Path,
    config_path: pathlib.Path,
    tmp_path: pathlib.Path,
    git_repo: GitSync,
) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        config = {
            "~/github_projects/": {
                "my_git_repo": {
                    "url": f"git+file://{git_repo.dir}",
                    "remotes": {"test_remote": f"git+file://{git_repo.dir}"},
                },
                "broken_repo": {
                    "url": f"git+file://{git_repo.dir}",
                    "remotes": {"test_remote": "git+file://non-existent-remote"},
                },
            }
        }
        yaml_config = config_path / ".vcspull.yaml"
        yaml_config_data = yaml.dump(config, default_flow_style=False)
        yaml_config.write_text(yaml_config_data, encoding="utf-8")

        # CLI can sync
        result = runner.invoke(cli, ["sync", "my_git_repo"])
        assert result.exit_code == 0
        output = "".join(list(result.output))
        assert "my_git_repo" in output
