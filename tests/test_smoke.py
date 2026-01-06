def test_can_import_package_modules():
    # Basic smoke tests for imports
    import fbcm  # noqa: F401
    import fbcm.base  # noqa: F401
    import fbcm.fbcm  # noqa: F401
    import fbcm.nfl  # noqa: F401


def test_cli_help_exits_cleanly():
    from click.testing import CliRunner

    from fbcm.fbcm import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])  # Should not perform side effects
    assert result.exit_code == 0
    # Sanity check that top-level command name appears in help
    assert "Usage" in result.output
