import os

SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret-change-me-please-32bytes")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./finance.db")
ACCESS_MIN = int(os.getenv("ACCESS_TOKEN_MINUTES", "30"))
REFRESH_DAYS = int(os.getenv("REFRESH_TOKEN_DAYS", "7"))
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024
MAX_ROWS = int(os.getenv("MAX_ROWS", "50000"))
