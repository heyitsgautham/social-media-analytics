# 📊 Social Media Analytics Platform

A real-time social media analytics platform that processes user engagement data, provides trending hashtag insights, and scales efficiently using modern backend technologies.

## 🎯 Purpose

This platform demonstrates end-to-end engineering workflows with a focus on:
- **Real-time analytics**: Trending hashtag detection with sliding window counters
- **Deep insights**: Comment thread analysis and viral chain detection  
- **Engagement reports**: Complex SQL aggregations for user and content analytics
- **Scalable architecture**: Redis caching, retry mechanisms, and fault tolerance
- **Production-ready**: FastAPI + SQLAlchemy + Alembic + comprehensive testing

## 🏗️ Architecture

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   FastAPI App   │      │    Typer CLI    │      │   PostgreSQL    │
│                 │      │                 │      │                 │
│ • REST API      │      │ • Seeding       │      │ • User data     │
│ • Health checks │      │ • Analytics     │      │ • Posts         │
│ • CORS enabled  │      │ • Reports       │      │ • Comments      │
└─────────┬───────┘      └─────────┬───────┘      │ • Hashtags      │
          │                        |              └─────────┬───────┘
          |                        |                        |
          │                        |                        | 
          └────────────────────────┴────────────────────────┘
                                   │
                                   │
                        ┌──────────────────────┐
                        │      Redis Cache     │
                        │                      │
                        │ • Trending data      │
                        │ • Sliding window     │
                        │ • TTL caching        │
                        └──────────────────────┘
```

### Core Components

- **Services Layer**: Business logic for trending analysis, comment processing, and reporting
- **Routes Layer**: FastAPI endpoints providing REST API access
- **CLI Layer**: Typer-based command-line interface for administration and analytics
- **Data Layer**: SQLAlchemy ORM models with Alembic migrations
- **Cache Layer**: Redis for high-performance trending data with configurable TTL

## 🚀 Setup Instructions

### Prerequisites

- Python 3.11+
- PostgreSQL 12+
- Redis (optional, for caching)

### 1. Clone Repository

```bash
git clone https://github.com/heyitsgautham/social-media-analytics.git
cd social-media-analytics
```

### 2. Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 3. Configure Environment

Create a `.env` file in the project root:

```env
# Database (required)
DATABASE_URL=postgresql+psycopg2://username:password@localhost:5432/social_analytics

# Redis Cache (optional)
ENABLE_REDIS_CACHE=true
REDIS_URL=redis://localhost:6379/0
TRENDING_TTL_SECONDS=60

# Retry Configuration (optional)
DB_RETRY_ATTEMPTS=3
DB_RETRY_MIN_WAIT=1
DB_RETRY_MAX_WAIT=10
```

### 4. Set Up Database

```bash
# Run migrations
alembic upgrade head

# Seed database with sample data (deterministic generation for reproducible demos)
python -m app.cli seed --users 1000 --posts 10000 --hashtags 150
```

### 5. Run Application

```bash
# Start FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or using Python module
python -m uvicorn app.main:app --reload
```

The API will be available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## 📋 Example Usage

### CLI Commands

#### Database Seeding
```bash
# Seed with default values (1000 users, 10000 posts, 150 hashtags)
python -m app.cli seed

# Seed with custom values
python -m app.cli seed --users 5000 --posts 50000 --hashtags 300
```

**Note**: The seeder uses deterministic random generation with fixed seeds (`random.seed(1337)` and `Faker.seed(1337)`), ensuring reproducible data for demos and testing. Running the seed command multiple times will generate identical data sets, making it perfect for consistent development environments and reproducible demonstrations.

#### Trending Analysis
```bash
# Get top 10 trending hashtags in last hour
python -m app.cli trending --window 60 --k 10

# Sync with database and show trending
python -m app.cli trending --sync --sync-minutes 120

# Get recommendations for a hashtag
python -m app.cli recommend --hashtag "python" --min-rate 0.1
```

#### Comment Analysis
```bash
# Analyze comment thread depths
python -m app.cli comment-depths

# Detect viral comment chains
python -m app.cli viral-chains --min-depth 5 --min-engagement 100
```

#### Engagement Reports
```bash
# Top 10 most engaged users
python -m app.cli top-users --limit 10

# Top hashtags by post count
python -m app.cli top-hashtags --limit 20

# Fastest growing hashtags in last 24 hours
python -m app.cli fastest-growing --hours 24 --limit 15
```

### API Examples

#### Health Check
```bash
curl -X GET "http://localhost:8000/health"
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-09-20T10:30:00Z",
  "database": "connected",
  "cache": "connected"
}
```

#### Trending Hashtags
```bash
# Get trending hashtags
curl -X GET "http://localhost:8000/hashtags/trending?window_minutes=60&k=5"
```

**Response:**
```json
{
  "hashtags": [
    {"hashtag": "python", "count": 145},
    {"hashtag": "datascience", "count": 89},
    {"hashtag": "ai", "count": 67},
    {"hashtag": "machinelearning", "count": 54},
    {"hashtag": "tech", "count": 42}
  ],
  "window_minutes": 60,
  "total_count": 5
}
```

#### Hashtag Recommendations
```bash
curl -X GET "http://localhost:8000/hashtags/recommendations?target_hashtag=python&min_cooccurrence_rate=0.1"
```

**Response:**
```json
{
  "target_hashtag": "python",
  "recommendations": [
    {"hashtag": "programming", "cooccurrence_rate": 0.85},
    {"hashtag": "coding", "cooccurrence_rate": 0.72},
    {"hashtag": "developer", "cooccurrence_rate": 0.45}
  ],
  "min_cooccurrence_rate": 0.1
}
```

#### Comment Analysis
```bash
# Get comment depth analysis
curl -X GET "http://localhost:8000/comments/depth-analysis"

# Get viral comment chains
curl -X GET "http://localhost:8000/comments/viral-chains?min_depth=3&min_engagement=50"
```

#### Engagement Reports
```bash
# Get top engaged users
curl -X GET "http://localhost:8000/reports/top-users?limit=10"

# Get top hashtags
curl -X GET "http://localhost:8000/reports/top-hashtags?limit=20"

# Get fastest growing hashtags
curl -X GET "http://localhost:8000/reports/fastest-growing?hours=24&limit=15"
```

**Top Users Response:**
```json
{
  "users": [
    {
      "user_id": 42,
      "username": "alice_data",
      "total_engagement": 1250,
      "post_count": 34,
      "avg_engagement_per_post": 36.76
    }
  ],
  "limit": 10,
  "total_count": 1
}
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test modules
pytest tests/test_trending.py
pytest tests/test_comments.py
pytest tests/test_reports.py
```

## 📊 Screenshots

*Screenshots and visual demonstrations would be added here to showcase:*

- *Swagger UI documentation interface*
- *CLI command outputs*
- *Sample API responses*
- *Dashboard views (if frontend is implemented)*

## 🛠️ Development

### Project Structure

```
app/
├── __init__.py
├── main.py              # FastAPI application factory
├── config.py            # Environment configuration
├── db.py               # Database session management
├── models.py           # SQLAlchemy ORM models
├── cli.py              # Typer CLI commands
├── routes/             # FastAPI route handlers
│   ├── hashtags.py     # Trending and recommendation endpoints
│   ├── comments.py     # Comment analysis endpoints
│   ├── reports.py      # Engagement report endpoints
│   └── health.py       # Health check endpoint
└── services/           # Business logic layer
    ├── seeder.py       # Database seeding utilities
    ├── trending.py     # Hashtag trending engine
    ├── comments.py     # Comment analysis algorithms
    └── reports.py      # Engagement reporting logic

migrations/             # Alembic database migrations
tests/                  # Pytest test suite
```

### Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'feat: add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🏗️ Milestones Completed

- ✅ **Milestone 0**: Repository bootstrap and CI setup
- ✅ **Milestone 1**: SQLAlchemy schema and Alembic migrations
- ✅ **Milestone 2**: Faker-powered dataset seeding
- ✅ **Milestone 3**: Trending hashtag engine with Redis caching
- ✅ **Milestone 4**: Comment depth analysis and viral chain detection
- ✅ **Milestone 5**: Complex engagement reports with SQL aggregations
- ✅ **Milestone 6**: System design improvements (caching, retries, fault tolerance)
- ✅ **Milestone 7**: Demo polish and comprehensive documentation

---

*Built with ❤️ using FastAPI, SQLAlchemy, PostgreSQL, and Redis*
