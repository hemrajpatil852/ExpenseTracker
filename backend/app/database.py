from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DATABASE_URL

url = DATABASE_URL
# Normalise every common Postgres spelling to the driver we install (psycopg2)
for prefix in ("postgres://", "postgresql+psycopg://", "postgresql+psycopg2://"):
    if url.startswith(prefix):
        url = "postgresql://" + url[len(prefix):]
        break

kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {"pool_pre_ping": True}
engine = create_engine(url, **kwargs)


if url.startswith("sqlite"):  # SQLite ignores FK cascades unless asked
    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
