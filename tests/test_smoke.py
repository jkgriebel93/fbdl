def test_can_import_package_modules():
    # Basic smoke tests for imports
    import fbdl  # noqa: F401
    import fbdl.base  # noqa: F401
    import fbdl.fbdl  # noqa: F401
    import fbdl.nfl  # noqa: F401


def test_cli_help_exits_cleanly():
    from click.testing import CliRunner

    from fbdl.fbdl import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])  # Should not perform side effects
    assert result.exit_code == 0
    # Sanity check that top-level command name appears in help
    assert "Usage" in result.output
