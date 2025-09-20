# app/cli.py
from typing import Optional

import typer

from app.db import get_session
from app.services import seeder
from app.services.trending import populate_trending_from_db, recommendation_engine, trending_engine

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


@app.command("trending")
def trending_cmd(
    window: int = typer.Option(
        60, "--window", "-w", help="Time window in minutes (1-1440)", min=1, max=1440
    ),
    k: int = typer.Option(
        10, "--k", "-k", help="Number of top hashtags to return (1-100)", min=1, max=100
    ),
    sync: bool = typer.Option(False, "--sync", help="Sync with database before showing trending"),
    sync_minutes: int = typer.Option(
        60, "--sync-minutes", help="Minutes of data to sync from database", min=1, max=1440
    ),
):
    """Get trending hashtags within specified time window."""
    try:
        # Sync with database if requested
        if sync:
            typer.echo(f"Syncing trending data from last {sync_minutes} minutes...")
            populate_trending_from_db(minutes_back=sync_minutes)
            typer.echo("✓ Sync complete")

        # Get trending hashtags
        trending_data = trending_engine.top(k=k, window_minutes=window)

        if not trending_data:
            typer.echo(f"No trending hashtags found in the last {window} minutes")
            return

        typer.echo(f"\n🔥 Top {len(trending_data)} trending hashtags (last {window} minutes):")
        typer.echo("─" * 50)

        for i, (hashtag, count) in enumerate(trending_data, 1):
            typer.echo(f"{i:2d}. #{hashtag:<20} ({count:,} posts)")

        typer.echo(f"\nTotal hashtags tracked: {len(trending_engine.counters)}")

    except Exception as e:
        typer.echo(f"❌ Error getting trending hashtags: {e}", err=True)
        raise typer.Exit(1)


@app.command("recommend")
def recommend_cmd(
    hashtag: str = typer.Argument(..., help="Target hashtag (without # symbol)"),
    max_recommendations: int = typer.Option(
        3, "--max", "-m", help="Maximum recommendations (1-10)", min=1, max=10
    ),
):
    """Get hashtag recommendations based on co-occurrence patterns."""
    try:
        # Remove # if present
        clean_hashtag = hashtag.lstrip("#")

        # Get recommendations
        recommendations = recommendation_engine.get_recommendations(
            hashtag=clean_hashtag, max_recommendations=max_recommendations
        )

        if not recommendations:
            typer.echo(f"No recommendations found for #{clean_hashtag}")
            typer.echo("This could mean:")
            typer.echo("• The hashtag doesn't exist in the database")
            typer.echo("• No other hashtags co-occur ≥30% of the time")
            return

        typer.echo(f"\n💡 Hashtag recommendations for #{clean_hashtag}:")
        typer.echo("─" * 50)

        for i, (rec_hashtag, rate) in enumerate(recommendations, 1):
            typer.echo(f"{i}. #{rec_hashtag:<20} ({rate:.1%} co-occurrence)")

        typer.echo(
            f"\nMinimum co-occurrence rate: {recommendation_engine.min_cooccurrence_rate:.1%}"
        )

    except Exception as e:
        typer.echo(f"❌ Error getting recommendations: {e}", err=True)
        raise typer.Exit(1)


@app.command("trending-status")
def trending_status_cmd():
    """Show trending engine status and health metrics."""
    try:
        status = trending_engine.get_status()

        typer.echo("\n📊 Trending Engine Status:")
        typer.echo("─" * 30)
        typer.echo(f"Total hashtags tracked: {status['total_hashtags']:,}")
        typer.echo(f"Total minute buckets:   {status['total_buckets']:,}")
        typer.echo(f"Current minute:         {status['current_minute']}")
        typer.echo(f"Window size:            {status['window_minutes']} minutes")

        # Calculate some additional metrics
        avg_buckets = status["total_buckets"] / max(status["total_hashtags"], 1)
        typer.echo(f"Avg buckets per tag:    {avg_buckets:.1f}")

        if status["total_hashtags"] > 0:
            typer.echo("\n✓ Engine is active and tracking hashtags")
        else:
            typer.echo("\n⚠️  Engine has no active hashtags")
            typer.echo("Consider running 'trending --sync' to populate from database")

    except Exception as e:
        typer.echo(f"❌ Error getting engine status: {e}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
