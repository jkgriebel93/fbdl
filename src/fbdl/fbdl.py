import click

from .base import MetaDataUpdater
from .nfl import NFLShowDownloader



@click.group()
def cli():
    pass


@click.command()
@click.argument("directory_path", type=click.Path(exists=True))
@click.option("--pretend", default=False, is_flag=True)
@click.option("--verbose", default=False, is_flag=True)
def update_metadata(directory_path, pretend, verbose):
    md_updater = MetaDataUpdater(directory_path, pretend, verbose)
    md_updater.iter_and_update_children()


@click.command()
@click.argument("episode_names_file")
@click.option("--cookies")
@click.option("--show-dir")
def nfl_show(episode_names_file, cookies, show_dir):
    click.echo("Downloading NFL show")
    nfl = NFLShowDownloader(episode_names_file, cookies, show_dir)
    nfl.download_episodes()

cli.add_command(nfl_show)
