# Social media analytics

A FastAPI service and a Typer CLI that analyze a social media dataset stored in PostgreSQL.
It ranks trending hashtags over a sliding time window, recommends hashtags that co-occur with a given one, walks nested comment threads, and builds engagement reports with SQL joins.
Redis caches the trending results when it is enabled.

[![CI](https://github.com/heyitsgautham/social-media-analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/heyitsgautham/social-media-analytics/actions/workflows/ci.yml)

## Requirements

| Tool | Version |
|---|---|
| Python | 3.11 or newer |
| PostgreSQL | 16 is what CI runs |
| Redis | 7, optional |
| [uv](https://docs.astral.sh/uv/) | any recent release, for the locked install |

Docker with Compose replaces all of the above if you only want to run the API.

## Quick start with Docker

```bash
docker compose up --build
```

Compose starts PostgreSQL, Redis and the API.
The API container applies the Alembic migrations before it starts serving on http://localhost:8000.
The database starts empty, so seed it from inside the container.

```bash
docker compose exec api python -m app.cli seed --users 200 --posts 1000 --hashtags 50
```

## Install for development

```bash
git clone https://github.com/heyitsgautham/social-media-analytics.git
cd social-media-analytics
uv sync --frozen
```

`uv sync --frozen` installs the exact versions in `uv.lock` into `.venv`, including the dev tools.
Without uv, `pip install -r requirements.txt -r requirements-dev.txt` installs the same pinned versions.
Both requirements files come from `uv export`, so regenerate them after any change to `uv.lock`.

## Configure

Copy the example file and edit it.

```bash
cp .env.example .env
```

`app/config.py` loads `.env` at import time.
Every variable is optional.

| Variable | Default | What it controls |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg2://app:app@localhost:5432/appdb` | PostgreSQL connection for the app and for Alembic |
| `ENABLE_REDIS_CACHE` | `false` | Caches top-k trending results in Redis when `true` |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `TRENDING_TTL_SECONDS` | `60` | Lifetime of a cached trending result |
| `DB_RETRY_ATTEMPTS` | `3` | Attempts for report and trending queries |
| `DB_RETRY_MIN_WAIT` | `1` | Shortest backoff between attempts, in seconds |
| `DB_RETRY_MAX_WAIT` | `10` | Longest backoff between attempts, in seconds |
| `LOG_LEVEL` | `INFO` | Level for the `app` logger |
| `LOG_FORMAT` | `json` | `json` writes one object per line to stderr, `text` writes plain lines |

## Run

Create the schema, load sample data, then start the API.

```bash
uv run alembic upgrade head
uv run python -m app.cli seed --users 200 --posts 1000 --hashtags 50
uv run uvicorn app.main:app --reload
```

`seed` uses a new random seed on every run.
Pass `--seed 1337` to get the same users, hashtags and posts each time on an empty database.
Posts carry the current time, so the trending window has data right after seeding.
`refresh --posts 100` adds more posts later to keep the window full.

Interactive API docs are at http://localhost:8000/docs.

### HTTP API

| Method and path | Returns |
|---|---|
| `GET /health/` | `ok`, `degraded` (Redis down) or `down` (database down), with detail per service |
| `GET /health/db` | Database status plus row counts for users, posts and hashtags |
| `GET /health/redis` | Redis status plus a set, get and delete round trip |
| `GET /hashtags/trending?window=60&k=10` | Top `k` hashtags in the last `window` minutes |
| `POST /hashtags/sync?minutes_back=60` | Loads recent posts from PostgreSQL into the trending engine |
| `GET /hashtags/status` | Hashtags and minute buckets the engine holds |
| `GET /hashtags/recommend/{hashtag}?max_recommendations=3` | Hashtags that appear on at least 30 percent of the target's posts |
| `GET /comments/depth/{post_id}` | Deepest reply level, comment and reply counts |
| `GET /comments/viral/{post_id}` | Longest chain where every comment has 3 or more replies or 10 or more upvotes |
| `GET /comments/tree/{post_id}` | The full comment thread as nested JSON |
| `GET /reports/most-engaged-users?limit=10` | Users ranked by engagements on their posts and comments |
| `GET /reports/top-hashtags?limit=10` | Hashtags ranked by distinct users |
| `GET /reports/fastest-growing-hashtags?hours=24&limit=10` | Share of each hashtag's posts that landed in the last `hours`, for hashtags with 5 or more posts |

FastAPI validates every query and path parameter and answers 422 when one is out of range.
A missing post returns 404.

```bash
curl -s -X POST "http://localhost:8000/hashtags/sync"
curl -s "http://localhost:8000/hashtags/trending?window=60&k=3"
```

The trending engine lives in the API process, so it starts empty.
Call `POST /hashtags/sync` once after seeding, or the trending endpoint returns an empty list.

### CLI

```bash
uv run python -m app.cli --help
```

| Command | What it does |
|---|---|
| `seed --users N --posts N --hashtags N [--seed N]` | Writes fake users, hashtags, posts, comment threads and engagements |
| `refresh --posts N` | Adds N new posts for the existing users and hashtags |
| `trending [--window 60] [--k 10] [--sync]` | Prints the top hashtags, syncing from the database when the engine is empty |
| `trending-status` | Prints the engine's hashtag and bucket counts |
| `recommend python [--max 3]` | Prints co-occurring hashtags |
| `comments depth --post ID` | Prints thread depth metrics for one post |
| `comments viral --post ID` | Prints the longest viral chain for one post |
| `reports users [--limit 10]` | Prints the most engaged users |
| `reports hashtags [--limit 10] [--hours 24]` | Prints top hashtags and the fastest growing ones |

## Test

The suite runs against a real PostgreSQL database and a real Redis.
Many tests delete every row before they run, so point `DATABASE_URL` at a database you can wipe.

```bash
docker compose up -d db redis
createdb -h localhost -U app testdb
export DATABASE_URL=postgresql+psycopg2://app:app@localhost:5432/testdb
export ENABLE_REDIS_CACHE=true REDIS_URL=redis://localhost:6379/0
uv run alembic upgrade head
uv run pytest --cov=app
```

The Compose database user and password are both `app`.
Any local PostgreSQL and Redis work the same way.
Coverage of `app/` must stay at 85 percent or above, set in `pyproject.toml`.

Lint, format and type checks:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

`uv run pre-commit install` runs the same checks before each commit.

## Architecture

```
app/
  main.py            FastAPI app factory, request logging middleware, error handlers
  cli.py             Typer CLI over the same services
  config.py          Environment variables
  db.py              SQLAlchemy engine and a commit-or-rollback session context manager
  models.py          SQLAlchemy 2.0 models and indexes
  logging_config.py  JSON log formatter
  routes/            HTTP layer, Pydantic response models and parameter validation
  services/
    trending.py      Sliding window counters, Redis cache, co-occurrence recommendations
    comments.py      Recursive depth analysis and backtracking viral chain search
    reports.py       Engagement reports in SQL, plus a transactional engagement insert
    seeder.py        Faker data generator
migrations/          Alembic revisions
tests/               pytest suite, mostly against PostgreSQL
```

The routes and the CLI are thin.
Both call the same functions in `app/services/`, which take a SQLAlchemy session.

**Trending.**
`TrendingEngine` keeps a count per hashtag per minute in memory and drops buckets older than its window.
`top(k, window)` sums the buckets inside the window.
With Redis enabled it caches each `(window, k)` result for `TRENDING_TTL_SECONDS`, and it falls back to memory alone when Redis is unreachable.
`populate_trending_from_db` fills the buckets from posts created in the last N minutes.

**Recommendations.**
For a target hashtag, the engine counts how many of its posts also carry each other hashtag.
It returns those whose share is at least 30 percent.

**Comments.**
Depth analysis walks each thread recursively with memoized subtree depths.
Viral chain search backtracks from every root comment that meets the viral rule and keeps the longest path.

**Reports.**
Each report is one SQL query with joins and aggregates.
Report and trending queries retry with exponential backoff through tenacity.

**Schema.**
Tables hold users, posts, hashtags, the post to hashtag link, comments and engagements.
A `hashtag_cooccurrence` table exists in the schema, but no code reads or writes it yet.
Indexes cover the hot paths, including `posts(user_id, created_at)`, `post_hashtags(hashtag_id, post_id)`, `comments(parent_id)` and `engagements(target_type, target_id, created_at)`.
CI runs `alembic check`, so a model change without a migration fails the build.

<img width="1284" height="1098" alt="Entity relationship diagram" src="https://github.com/user-attachments/assets/324bfc88-9116-4688-b3ea-ccb3346912d1" />

**Logging and errors.**
The `app` logger writes JSON lines to stderr.
Every request logs its method, path, status and duration.
Unhandled exceptions log their traceback and return a 500 body with an `error_code`.

## CI

`.github/workflows/ci.yml` runs on every push to `main` and every pull request.

| Job | Steps |
|---|---|
| Lint and typecheck | `uv lock --check`, ruff lint, ruff format check, mypy |
| Tests with coverage | Migrations, `alembic check`, pytest with the 85 percent gate, against PostgreSQL 16 and Redis 7 services |
| Dependency audit | `pip-audit --strict` on the locked environment |
| Secret scan | gitleaks over the full history |

Dependabot opens weekly update pull requests for the uv lockfile and the GitHub Actions versions.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
