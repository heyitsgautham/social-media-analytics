# Social Media Analytics Platform - Demo Script

**Estimated Time**: 5 minutes  
**Purpose**: Demonstrate core features and capabilities of the platform

---

## 🎬 Demo Overview

This demo showcases:
1. Database seeding with realistic data
2. CLI-based analytics commands
3. REST API endpoints
4. Real-time trending analysis
5. Comment depth analysis
6. Engagement reporting

---

## 📋 Pre-Demo Setup

### 1. Environment Check
```bash
# Verify Python environment
python --version  # Should be 3.11+

# Check if virtual environment is active
which python

# Verify dependencies
pip list | grep -E "(fastapi|sqlalchemy|typer|redis)"
```

### 2. Database Connection
```bash
# Test database connection
python -c "from app.db import get_session; print('Database: OK')"

# Check migration status
alembic current
alembic heads
```

### 3. Optional: Start Redis (for caching demo)
```bash
# If Redis is available
redis-server --daemonize yes
redis-cli ping  # Should return "PONG"
```

---

## 🚀 Demo Script

### Step 1: Database Seeding (1 minute)

```bash
# Clear any existing data (optional)
# python -c "from app.db import engine; from app.models import Base; Base.metadata.drop_all(engine); Base.metadata.create_all(engine)"

# Seed database with sample data
echo "🌱 Seeding database with sample data..."
python -m app.cli seed --users 500 --posts 2000 --hashtags 100

# Verify seeding
python -c "
from app.db import get_session
from app.models import User, Post, Hashtag, Comment, Engagement
with get_session() as db:
    print(f'Users: {db.query(User).count()}')
    print(f'Posts: {db.query(Post).count()}')
    print(f'Hashtags: {db.query(Hashtag).count()}')
    print(f'Comments: {db.query(Comment).count()}')
    print(f'Engagements: {db.query(Engagement).count()}')
"
```

**Expected Output:**
```
🌱 Seeding database with sample data...
Seed complete: users=500, posts=2000, hashtags=100
Users: 500
Posts: 2000
Hashtags: 100
Comments: ~1200
Engagements: ~4000
```

### Step 2: CLI Analytics Demo (2 minutes)

#### Trending Hashtags Analysis
```bash
echo "📈 Getting trending hashtags..."
python -m app.cli trending --window 60 --k 10

echo "📈 Syncing with database and showing trending..."
python -m app.cli trending --sync --sync-minutes 120 --k 5
```

**Expected Output:**
```
📈 Getting trending hashtags...
Top 5 trending hashtags (60-minute window):
1. #python (45 mentions)
2. #tech (38 mentions)
3. #ai (32 mentions)
4. #coding (28 mentions)
5. #data (24 mentions)
```

#### Comment Analysis
```bash
echo "🔍 Analyzing comment thread depths..."
python -m app.cli comment-depths

echo "🔍 Detecting viral comment chains..."
python -m app.cli viral-chains --min-depth 3 --min-engagement 50
```

**Expected Output:**
```
🔍 Analyzing comment thread depths...
Comment Depth Analysis:
- Depth 1: 450 comments
- Depth 2: 180 comments  
- Depth 3: 45 comments
- Depth 4+: 12 comments
Maximum depth: 6

🔍 Detecting viral comment chains...
Found 3 viral comment chains:
- Chain 1: Post #123, 5 levels deep, 847 total engagement
- Chain 2: Post #456, 4 levels deep, 523 total engagement
```

#### Engagement Reports
```bash
echo "👥 Top engaged users..."
python -m app.cli top-users --limit 5

echo "🏷️ Top hashtags by usage..."
python -m app.cli top-hashtags --limit 10

echo "🚀 Fastest growing hashtags..."
python -m app.cli fastest-growing --hours 24 --limit 5
```

### Step 3: REST API Demo (2 minutes)

#### Start the API Server
```bash
echo "🌐 Starting FastAPI server..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
SERVER_PID=$!

# Wait for server to start
sleep 3

# Test server is running
curl -s http://localhost:8000/health | python -m json.tool
```

#### Health Check
```bash
echo "💓 Health check..."
curl -s "http://localhost:8000/health" | python -m json.tool
```

**Expected Output:**
```json
{
  "status": "healthy",
  "timestamp": "2025-09-20T10:30:00Z",
  "database": "connected",
  "cache": "connected"
}
```

#### Trending Hashtags API
```bash
echo "📈 API: Getting trending hashtags..."
curl -s "http://localhost:8000/hashtags/trending?window_minutes=60&k=5" | python -m json.tool
```

**Expected Output:**
```json
{
  "hashtags": [
    {"hashtag": "python", "count": 45},
    {"hashtag": "tech", "count": 38},
    {"hashtag": "ai", "count": 32},
    {"hashtag": "coding", "count": 28},
    {"hashtag": "data", "count": 24}
  ],
  "window_minutes": 60,
  "total_count": 5
}
```

#### Hashtag Recommendations API
```bash
echo "🎯 API: Getting hashtag recommendations..."
curl -s "http://localhost:8000/hashtags/recommendations?target_hashtag=python&min_cooccurrence_rate=0.1" | python -m json.tool
```

**Expected Output:**
```json
{
  "target_hashtag": "python",
  "recommendations": [
    {"hashtag": "programming", "cooccurrence_rate": 0.75},
    {"hashtag": "coding", "cooccurrence_rate": 0.68},
    {"hashtag": "developer", "cooccurrence_rate": 0.45}
  ],
  "min_cooccurrence_rate": 0.1
}
```

#### Comment Analysis API
```bash
echo "🔍 API: Comment depth analysis..."
curl -s "http://localhost:8000/comments/depth-analysis" | python -m json.tool

echo "🔍 API: Viral comment chains..."
curl -s "http://localhost:8000/comments/viral-chains?min_depth=3&min_engagement=50" | python -m json.tool
```

#### Engagement Reports API
```bash
echo "👥 API: Top engaged users..."
curl -s "http://localhost:8000/reports/top-users?limit=5" | python -m json.tool

echo "🏷️ API: Top hashtags..."
curl -s "http://localhost:8000/reports/top-hashtags?limit=10" | python -m json.tool

echo "🚀 API: Fastest growing hashtags..."
curl -s "http://localhost:8000/reports/fastest-growing?hours=24&limit=5" | python -m json.tool
```

**Top Users Expected Output:**
```json
{
  "users": [
    {
      "user_id": 42,
      "username": "alice_data",
      "total_engagement": 1250,
      "post_count": 34,
      "avg_engagement_per_post": 36.76
    },
    {
      "user_id": 157,
      "username": "bob_analytics",
      "total_engagement": 980,
      "post_count": 28,
      "avg_engagement_per_post": 35.0
    }
  ],
  "limit": 5,
  "total_count": 2
}
```

#### Trending Engine Status
```bash
echo "⚙️ API: Engine status..."
curl -s "http://localhost:8000/hashtags/status" | python -m json.tool
```

**Expected Output:**
```json
{
  "total_hashtags": 100,
  "total_buckets": 1440,
  "cache_size_mb": 2.5,
  "oldest_bucket_age_minutes": 60
}
```

### Step 4: Interactive Demo (Optional)

#### Open Swagger UI
```bash
echo "📖 Opening API documentation..."
echo "Visit: http://localhost:8000/docs"
echo "Alternative: http://localhost:8000/redoc"
```

#### Test Custom Queries
```bash
# Try different window sizes
curl -s "http://localhost:8000/hashtags/trending?window_minutes=30&k=3" | python -m json.tool

# Test different recommendation thresholds
curl -s "http://localhost:8000/hashtags/recommendations?target_hashtag=ai&min_cooccurrence_rate=0.2" | python -m json.tool
```

### Step 5: Cleanup
```bash
echo "🧹 Stopping demo server..."
kill $SERVER_PID 2>/dev/null || true

echo "🧹 Demo completed successfully!"
```

---

## 🎯 Demo Talking Points

### Architecture Highlights
- **Microservices**: Separate concerns (trending, comments, reports)
- **Caching**: Redis for high-performance trending data
- **Fault Tolerance**: Retry mechanisms and graceful degradation
- **Type Safety**: Pydantic models and SQLAlchemy typing

### Performance Features
- **Sliding Window**: Efficient hashtag counting with time windows
- **Bulk Operations**: Optimized database seeding and queries
- **Connection Pooling**: SQLAlchemy session management
- **TTL Caching**: Configurable cache expiration

### Scalability Considerations
- **Horizontal Scaling**: Stateless API design
- **Database Optimization**: Proper indexing and query optimization
- **Cache Strategy**: Redis clustering support
- **Monitoring**: Health checks and status endpoints

### Production Readiness
- **Error Handling**: Comprehensive exception management
- **Logging**: Structured logging (can be enhanced)
- **Configuration**: Environment-based settings
- **Testing**: Comprehensive test suite with pytest

---

## 🔧 Troubleshooting

### Common Issues

1. **Database Connection Error**
   ```bash
   # Check DATABASE_URL in .env
   echo $DATABASE_URL
   # Test connection
   psql $DATABASE_URL -c "SELECT version();"
   ```

2. **Redis Connection Error**
   ```bash
   # Check if Redis is running
   redis-cli ping
   # Or disable Redis caching
   export ENABLE_REDIS_CACHE=false
   ```

3. **Port Already in Use**
   ```bash
   # Use different port
   uvicorn app.main:app --port 8001
   ```

4. **Import Errors**
   ```bash
   # Ensure PYTHONPATH is set
   export PYTHONPATH=.
   # Or use module execution
   python -m app.cli --help
   ```

---

## 📊 Demo Success Metrics

- ✅ Database seeded with 500+ users, 2000+ posts
- ✅ CLI commands execute without errors
- ✅ API endpoints return valid JSON responses
- ✅ Trending analysis shows reasonable results
- ✅ Comment analysis detects thread structures
- ✅ Reports generate engagement statistics
- ✅ Health checks pass for all components

*Demo completed in under 5 minutes with comprehensive feature coverage!*