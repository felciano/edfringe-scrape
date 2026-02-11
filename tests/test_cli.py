"""Tests for CLI commands."""

from click.testing import CliRunner

from edfringe_scrape.cli import cli


class TestCLI:
    """Test CLI commands."""

    def test_cli_help(self) -> None:
        """Test CLI help output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_info_command(self) -> None:
        """Test info command output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["info"])
        assert result.exit_code == 0
        assert "Debug mode:" in result.output

    def test_verbose_flag(self) -> None:
        """Test verbose flag is accepted."""
        runner = CliRunner()
        result = runner.invoke(cli, ["-v", "info"])
        assert result.exit_code == 0
