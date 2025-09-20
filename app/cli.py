# app/cli.py
import typer
from app.db import get_session
from app.services import seeder

app = typer.Typer(help="Social Analytics CLI with subcommands")

@app.command("seed")
def seed_cmd(
    users: int = typer.Option(1000, help="Number of users"),
    posts: int = typer.Option(10000, help="Number of posts"),
    hashtags: int = typer.Option(150, help="Number of unique hashtags"),
):
    """Populate the database with mock data."""
    with get_session() as db:
        us = seeder.make_users(db, users)
        tags = seeder.make_hashtags(db, hashtags)
        ps = seeder.make_posts(db, us, tags, posts)
        seeder.make_comments(db, ps, us, frac_with_threads=0.6)
        seeder.make_engagements(db, ps, us)
    typer.echo(f"Seed complete: users={users}, posts={posts}, hashtags={hashtags}")

# add a tiny extra command to force multi-command mode in help
@app.command("hello")
def hello(name: str = "world"):
    """Sanity check command."""
    typer.echo(f"hello, {name}")

if __name__ == "__main__":
    app()
