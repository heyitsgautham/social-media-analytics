import os

from dotenv import load_dotenv

load_dotenv()

# Logging: LOG_FORMAT is "json" (one object per line) or "text"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "json").lower()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://app:app@localhost:5432/appdb")

# Redis cache configuration
ENABLE_REDIS_CACHE = os.getenv("ENABLE_REDIS_CACHE", "false").lower() in ("true", "1", "yes")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
TRENDING_TTL_SECONDS = int(os.getenv("TRENDING_TTL_SECONDS", "60"))

# Retry configuration
DB_RETRY_ATTEMPTS = int(os.getenv("DB_RETRY_ATTEMPTS", "3"))
DB_RETRY_MIN_WAIT = int(os.getenv("DB_RETRY_MIN_WAIT", "1"))
DB_RETRY_MAX_WAIT = int(os.getenv("DB_RETRY_MAX_WAIT", "10"))
