"""
Database layer – SQLAlchemy engine, session factory, and schema bootstrap.
"""

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    Float,
    Boolean,
    Text,
    DateTime,
    func,
)
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.config import DATABASE_URL

# ──────────────────────────── Engine & Session ───────────────────────────
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ──────────────────────────── ORM Models ─────────────────────────────────
class Interaction(Base):
    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    item_id = Column(Integer, nullable=False)
    rating = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    is_drifted = Column(Boolean, default=False)


class ModelRegistry(Base):
    __tablename__ = "model_registry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(Integer, unique=True, nullable=False)
    health_score = Column(Float)
    train_loss = Column(Float)
    val_loss = Column(Float)
    is_active = Column(Boolean, default=False)
    model_path = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class HealingEvent(Base):
    __tablename__ = "healing_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(Text)
    description = Column(Text)
    old_version = Column(Integer)
    new_version = Column(Integer)
    old_score = Column(Float)
    new_score = Column(Float)
    action_taken = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SystemMetric(Base):
    __tablename__ = "system_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    health_score = Column(Float)
    drift_score = Column(Float)
    drift_detected = Column(Boolean)
    grad_norm = Column(Float)
    current_lr = Column(Float)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())


class Movie(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    movie_id = Column(Integer, unique=True, nullable=False)   # original ML id (0-based)
    title = Column(Text, nullable=False)
    year = Column(Integer)
    genres = Column(Text)  # pipe-separated, e.g. "Action|Sci-Fi"



# ──────────────────────────── Helpers ────────────────────────────────────
def get_db_connection():
    """Return a new SQLAlchemy session (caller must close)."""
    return SessionLocal()


def init_db():
    """Create all tables if they do not already exist."""
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables initialised.")
