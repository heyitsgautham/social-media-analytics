# Demo script

A five minute walk through the CLI and the HTTP API on seeded data.
Every output below comes from one real run with `--seed 1337` on an empty database.
Row IDs, timestamps and engagement totals will differ on your machine.

## Before you start

Follow "Install for development" and "Configure" in the [README](README.md), or run `docker compose up --build` and prefix each CLI command with `docker compose exec api`.
Set `LOG_FORMAT=text` if you want readable log lines in the terminal.

```bash
uv run alembic upgrade head
```

## 1. Seed the database

```bash
uv run python -m app.cli seed --users 200 --posts 1000 --hashtags 50 --seed 1337
```

```
Seed complete: users=200, posts=1000, hashtags=50
```

The seeder stamps every post with the current time, so the next step finds data in the last hour.

## 2. Trending hashtags

```bash
uv run python -m app.cli trending --sync --k 5
```

```
Syncing trending data from last 60 minutes...
✓ Sync complete

🔥 Top 5 trending hashtags (last 60 minutes):
──────────────────────────────────────────────────
 1. #ai                   (176 posts)
 2. #travel               (174 posts)
 3. #news                 (169 posts)
 4. #sports               (163 posts)
 5. #python               (155 posts)

Total hashtags tracked: 50
```

The seeder gives `ai`, `python`, `news`, `sports` and `travel` five times the weight of other tags, which is why they lead.

`recommend` lists hashtags that appear on at least 30 percent of a tag's posts.
Seeded tags are spread across 50 names, so none clear that bar and the command says so.

```bash
uv run python -m app.cli recommend ai
```

```
No recommendations found for #ai
This could mean:
• The hashtag doesn't exist in the database
• No other hashtags co-occur ≥30% of the time
```

## 3. Comment threads

Pick the post with the most replies.

```bash
psql "${DATABASE_URL/+psycopg2/}" -Atc \
  "select post_id from comments where parent_id is not null group by post_id order by count(*) desc limit 1"
```

Then analyze it, using the ID that query printed.

```bash
uv run python -m app.cli comments depth --post 2682
uv run python -m app.cli comments viral --post 2682
```

```
📊 Comment Depth Analysis for Post 2682:
──────────────────────────────────────────────────
Max depth:              3
Total comments:         14
Total replies:          11
Avg replies/comment:    0.79

💬 Comments have 3 levels of nesting

🔥 Viral Chain Analysis for Post 2682:
──────────────────────────────────────────────────
Longest chain length:   3
Total viral chains:     5
Viral criteria met:     ✓

Viral criteria: ≥3 replies OR ≥10 upvotes per comment

🏆 Longest viral chain (comments):
  1. Comment #5339
  2. Comment #5340
  3. Comment #5341
```

## 4. Engagement reports

```bash
uv run python -m app.cli reports users --limit 3
```

```
👥 Top 3 Most Engaged Users:
────────────────────────────────────────────────────────────────────────────────
#   Handle               Total    Posts    Comments P Count  C Count
────────────────────────────────────────────────────────────────────────────────
1   @amanda49            519      519      0        9        19
2   @adriennejohnson     495      495      0        11       17
3   @janetmartin         495      495      0        10       16
────────────────────────────────────────────────────────────────────────────────
Total engagements: 1,509
Average per user:  503.0
```

The seeder only creates engagements on posts, so the comment engagement column stays at 0.

```bash
uv run python -m app.cli reports hashtags --limit 3
```

This prints the top hashtags by distinct users, then the fastest growing ones.
Right after seeding every post is recent, so every growth rate is 100 percent.

## 5. The HTTP API

```bash
uv run uvicorn app.main:app
```

In a second terminal:

```bash
curl -s http://localhost:8000/health/
curl -s -X POST http://localhost:8000/hashtags/sync
curl -s "http://localhost:8000/hashtags/trending?window=60&k=3"
```

```json
{"status":"ok","db":{"status":"ok"},"redis":{"status":"ok"},"version":"1.0.0","timestamp":"2026-10-24T21:15:00.382922"}
{"message":"Successfully synced trending data from last 60 minutes","minutes_back":60,"status":"success"}
{"hashtags":[{"hashtag":"ai","count":176},{"hashtag":"travel","count":174},{"hashtag":"news","count":169}],"window_minutes":60,"total_count":3}
```

The API process has its own trending engine, separate from the CLI's, which is why it needs its own sync.

The remaining endpoints are listed in the README, and http://localhost:8000/docs lets you call each one from the browser.

```bash
curl -s http://localhost:8000/comments/tree/2682
curl -s "http://localhost:8000/reports/most-engaged-users?limit=3"
curl -s "http://localhost:8000/reports/fastest-growing-hashtags?hours=24&limit=3"
```

## 6. Keep the window fresh

Posts age out of the 60 minute window.
`refresh` adds new posts for the existing users and hashtags.

```bash
uv run python -m app.cli refresh --posts 100
```

```
✅ Added 100 fresh posts to keep data current
```
