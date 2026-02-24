"""
FastAPI application – entrypoint for the Self-Healing Neural Recommendation System.
Phase 5: monitor, drift simulation, CORS for frontend dashboard.
"""

from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from backend.config import NUM_ITEMS, HEALTH_THRESHOLD
from backend.database import (
    init_db,
    get_db_connection,
    SystemMetric,
    HealingEvent,
    Movie,
)
from backend.data import seed_database, seed_movies, _item_to_movie, load_item_mapping
from backend.healer import HealingController
from backend.model import NeuralCollaborativeFiltering
from backend.registry import ModelRegistry
from backend.train import train_model


# ──────────────────────────── Globals ────────────────────────────────────
active_model: NeuralCollaborativeFiltering | None = None
healer = HealingController()


# ──────────────────────────── Lifespan ───────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialise DB & seed data.  Shutdown: stop auto-healer."""
    init_db()
    seed_database(drifted=False)
    seed_movies()
    load_item_mapping()
    yield
    healer.stop_auto_healing()


app = FastAPI(
    title="Self-Healing Neural Recommendation System",
    version="5.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────── Training & Recommend ───────────────────────────
@app.post("/train")
async def train_endpoint():
    """Kick off a training run, register the model, and return history."""
    global active_model
    result = train_model(drifted=False)

    model = NeuralCollaborativeFiltering()
    model.load_state_dict(torch.load(result["model_path"], weights_only=True))
    model.eval()
    active_model = model

    version = registry.save_version(model, {
        "health_score": max(0.0, 1.0 - result["final_val_loss"]) if result["final_val_loss"] else None,
        "train_loss": result["train_losses"][-1] if result["train_losses"] else None,
        "val_loss": result["final_val_loss"],
    })
    registry.set_active(version)
    result["registered_version"] = version

    return result


@app.get("/recommend")
async def recommend(user_id: int = Query(..., ge=0)):
    """Return top-10 item recommendations for the given user."""
    if active_model is None:
        return {"error": "No model trained yet. POST /train first."}

    with torch.no_grad():
        user_tensor = torch.tensor([user_id] * NUM_ITEMS, dtype=torch.long)
        item_tensor = torch.arange(NUM_ITEMS, dtype=torch.long)
        scores = active_model(user_tensor, item_tensor)

    top_items = torch.topk(scores, k=10)
    recommendations = [
        {"item_id": int(idx), "score": round(float(score), 4)}
        for idx, score in zip(top_items.indices, top_items.values)
    ]
    return {"user_id": user_id, "recommendations": recommendations}


# ──────────────────────── Movie Catalog Endpoints ────────────────────────
@app.get("/movies")
async def list_movies(genre: str | None = None, limit: int = 50, offset: int = 0):
    """List movies, optionally filtered by genre."""
    db = get_db_connection()
    try:
        q = db.query(Movie)
        if genre:
            q = q.filter(Movie.genres.ilike(f"%{genre}%"))
        total = q.count()
        rows = q.offset(offset).limit(limit).all()
        return {
            "total": total,
            "movies": [
                {
                    "movie_id": m.movie_id,
                    "title": m.title,
                    "year": m.year,
                    "genres": m.genres.split("|") if m.genres else [],
                }
                for m in rows
            ],
        }
    finally:
        db.close()


@app.get("/movies/genres")
async def list_genres():
    """Return all unique genres from the movie catalog."""
    db = get_db_connection()
    try:
        rows = db.query(Movie.genres).all()
        genre_set = set()
        for (g,) in rows:
            if g:
                for part in g.split("|"):
                    genre_set.add(part.strip())
        return sorted(genre_set)
    finally:
        db.close()


@app.get("/recommend/genre")
async def recommend_by_genre(
    genre: str = Query(...),
    user_id: int = Query(0, ge=0),
    limit: int = Query(20, le=100),
    liked: str = Query("", description="Comma-separated liked movie_ids")
):
    """
    Get recommendations filtered by genre.
    If model is trained, scores come from the NCF model.
    Otherwise, returns popular movies in that genre.
    """
    db = get_db_connection()
    try:
        # Get all movies matching the genre
        genre_movies = (
            db.query(Movie)
            .filter(Movie.genres.ilike(f"%{genre}%"))
            .all()
        )
        if not genre_movies:
            return {"genre": genre, "movies": []}

        if active_model is not None:
            # Score each genre movie using NCF
            # Build reverse map: movie_id -> item_id
            movie_to_item = {v: k for k, v in _item_to_movie.items()}
            
            user_profile_emb = None
            if liked:
                liked_ids = [int(x) for x in liked.split(",") if x.strip().isdigit()]
                liked_item_ids = [movie_to_item.get(m_id) for m_id in liked_ids if movie_to_item.get(m_id) is not None and movie_to_item.get(m_id) < NUM_ITEMS]
                
                if liked_item_ids:
                    with torch.no_grad():
                        items_tensor = torch.tensor(liked_item_ids, dtype=torch.long)
                        liked_embs = active_model.item_embedding(items_tensor)
                        user_profile_emb = liked_embs.mean(dim=0, keepdim=True)
                        
            scored = []
            for m in genre_movies:
                item_id = movie_to_item.get(m.movie_id)
                if item_id is not None and item_id < NUM_ITEMS:
                    with torch.no_grad():
                        if user_profile_emb is not None:
                           target_emb = active_model.item_embedding(torch.tensor([item_id], dtype=torch.long))
                           score = float(torch.nn.functional.cosine_similarity(user_profile_emb, target_emb).item())
                        else:
                           u = torch.tensor([user_id], dtype=torch.long)
                           i = torch.tensor([item_id], dtype=torch.long)
                           score = float(active_model(u, i).item())
                    scored.append((m, score))
            scored.sort(key=lambda x: x[1], reverse=True)
            results = scored[:limit]
        else:
            # No model: return movies sorted by year (newest first)
            genre_movies.sort(key=lambda m: m.year or 0, reverse=True)
            results = [(m, 0.0) for m in genre_movies[:limit]]

        return {
            "genre": genre,
            "movies": [
                {
                    "movie_id": m.movie_id,
                    "title": m.title,
                    "year": m.year,
                    "genres": m.genres.split("|") if m.genres else [],
                    "score": round(s, 4),
                }
                for m, s in results
            ],
        }
    finally:
        db.close()

@app.get("/recommend/similar")
async def recommend_similar(
    movie_id: int = Query(...),
    limit: int = Query(15, le=100)
):
    """
    Get recommendations similar to a specific movie using NCF embeddings.
    """
    db = get_db_connection()
    try:
        source_movie = db.query(Movie).filter(Movie.movie_id == movie_id).first()
        if not source_movie:
            return {"source": "Unknown", "movies": []}
            
        all_movies = db.query(Movie).all()
            
        if active_model is not None:
            movie_to_item = {v: k for k, v in _item_to_movie.items()}
            source_item_id = movie_to_item.get(movie_id)
            
            if source_item_id is not None and source_item_id < NUM_ITEMS:
                with torch.no_grad():
                    source_emb = active_model.item_embedding(torch.tensor([source_item_id], dtype=torch.long))
                    
                scored = []
                for m in all_movies:
                    if m.movie_id == movie_id:
                        continue
                    item_id = movie_to_item.get(m.movie_id)
                    if item_id is not None and item_id < NUM_ITEMS:
                        with torch.no_grad():
                            target_emb = active_model.item_embedding(torch.tensor([item_id], dtype=torch.long))
                            score = float(torch.nn.functional.cosine_similarity(source_emb, target_emb).item())
                            
                        # Boost score slightly if they share a genre
                        source_genres = set(source_movie.genres.split("|")) if source_movie.genres else set()
                        target_genres = set(m.genres.split("|")) if m.genres else set()
                        overlap = len(source_genres.intersection(target_genres))
                        if overlap > 0:
                            score += (overlap * 0.1)  # small boost for matching genres
                            
                        scored.append((m, score))
                
                scored.sort(key=lambda x: x[1], reverse=True)
                results = scored[:limit]
            else:
                scored = []
                source_genres = set(source_movie.genres.split("|")) if source_movie.genres else set()
                for m in all_movies:
                    if m.movie_id == movie_id:
                        continue
                    m_genres = set(m.genres.split("|")) if m.genres else set()
                    
                    # Ensure m_genres contains ALL genres in source_genres
                    if source_genres and source_genres.issubset(m_genres):
                        # Give a score based on how exact the match is (fewer extra genres = better score)
                        exactness_score = len(source_genres) / max(len(m_genres), 1)
                        scored.append((m, exactness_score))
                
                scored.sort(key=lambda x: x[1], reverse=True)
                results = scored[:limit]
        else:
            scored = []
            source_genres = set(source_movie.genres.split("|")) if source_movie.genres else set()
            for m in all_movies:
                if m.movie_id == movie_id:
                    continue
                m_genres = set(m.genres.split("|")) if m.genres else set()
                
                # Ensure m_genres contains ALL genres in source_genres
                if source_genres and source_genres.issubset(m_genres):
                    # Give a score based on how exact the match is (fewer extra genres = better score)
                    exactness_score = len(source_genres) / max(len(m_genres), 1)
                    scored.append((m, exactness_score))
                    
            scored.sort(key=lambda x: x[1], reverse=True)
            results = scored[:limit]

        return {
            "source": source_movie.title,
            "movies": [
                {
                    "movie_id": m.movie_id,
                    "title": m.title,
                    "year": m.year,
                    "genres": m.genres.split("|") if m.genres else [],
                    "score": round(s, 4),
                }
                for m, s in results
            ],
        }
    finally:
        db.close()


@app.get("/search")
async def search_movies(
    q: str = Query(..., description="Search query string for movie title"),
    limit: int = Query(20, le=100)
):
    """
    Search for movies by title.
    """
    if len(q.strip()) < 2:
        return {"query": q, "movies": []}
        
    db = get_db_connection()
    try:
        # Simple case-insensitive search on title
        movies = (
            db.query(Movie)
            .filter(Movie.title.ilike(f"%{q.strip()}%"))
            .limit(limit)
            .all()
        )
        
        return {
            "query": q,
            "movies": [
                {
                    "movie_id": m.movie_id,
                    "title": m.title,
                    "year": m.year,
                    "genres": m.genres.split("|") if m.genres else [],
                    "score": 0.0,
                }
                for m in movies
            ],
        }
    finally:
        db.close()


# ──────────────────────── Monitor Endpoints ──────────────────────────────
@app.get("/monitor/status")
async def monitor_status():
    """System health overview for the dashboard gauge."""
    db = get_db_connection()
    try:
        latest = (
            db.query(SystemMetric)
            .order_by(SystemMetric.id.desc())
            .first()
        )
        active = registry.get_active_version()
        return {
            "health_score": latest.health_score if latest else 0.0,
            "drift_score": latest.drift_score if latest else 0.0,
            "drift_detected": latest.drift_detected if latest else False,
            "grad_norm": latest.grad_norm if latest else 0.0,
            "current_lr": latest.current_lr if latest else 0.0,
            "active_version": active.get("version") if active else None,
            "recorded_at": latest.recorded_at.isoformat() if latest and latest.recorded_at else None,
        }
    finally:
        db.close()


@app.get("/monitor/drift")
async def monitor_drift():
    """Check current drift state from latest system metrics."""
    db = get_db_connection()
    try:
        latest = (
            db.query(SystemMetric)
            .order_by(SystemMetric.id.desc())
            .first()
        )
        return {
            "drift_score": latest.drift_score if latest else 0.0,
            "drift_detected": latest.drift_detected if latest else False,
            "health_score": latest.health_score if latest else 0.0,
        }
    finally:
        db.close()


@app.post("/simulate/drift")
async def simulate_drift():
    """Seed drifted MovieLens data and record drift in system_metrics."""
    seed_database(drifted=True)

    db = get_db_connection()
    try:
        # Record drift detection in system_metrics
        db.add(SystemMetric(
            health_score=0.4,  # simulated degradation
            drift_score=0.85,
            drift_detected=True,
            grad_norm=0.0,
            current_lr=0.0,
        ))
        db.add(HealingEvent(
            event_type="drift_simulated",
            description="Concept drift simulated with shifted MovieLens data",
            action_taken="drifted_data_seeded",
        ))
        db.commit()
    finally:
        db.close()

    return {"status": "drift_simulated", "message": "Drifted data seeded into PostgreSQL"}


# ──────────────────────── Healing Endpoints ──────────────────────────────
@app.post("/heal")
async def heal():
    """Run a single healing cycle and return the report."""
    report = healer.run_healing_cycle()

    if report.get("action") == "deployed":
        global active_model
        active_info = registry.get_active_version()
        if active_info:
            active_model = registry.load_version(active_info["version"])

    return report


@app.post("/heal/start")
async def heal_start(interval_seconds: int = 60):
    """Start the auto-healing background loop."""
    return healer.start_auto_healing(interval_seconds=interval_seconds)


@app.post("/heal/stop")
async def heal_stop():
    """Stop the auto-healing background loop."""
    return healer.stop_auto_healing()


# ──────────────────────── Registry Endpoints ─────────────────────────────
@app.get("/registry")
async def get_registry():
    """List all registered model versions."""
    return registry.get_all_versions()


@app.post("/rollback")
async def rollback():
    """Roll back to the previous model version."""
    global active_model
    result = registry.rollback()
    active_model = registry.load_version(result["rolled_back_to"])
    return result


# ──────────────────────── Events & Metrics ───────────────────────────────
@app.get("/events")
async def get_events():
    """Return the last 50 healing events from PostgreSQL."""
    db = get_db_connection()
    try:
        rows = (
            db.query(HealingEvent)
            .order_by(HealingEvent.created_at.desc())
            .limit(50)
            .all()
        )
        return [
            {
                "id": e.id,
                "event_type": e.event_type,
                "description": e.description,
                "old_version": e.old_version,
                "new_version": e.new_version,
                "old_score": e.old_score,
                "new_score": e.new_score,
                "action_taken": e.action_taken,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in rows
        ]
    finally:
        db.close()


@app.get("/metrics/history")
async def metrics_history():
    """Return the last 50 system_metrics rows from PostgreSQL."""
    db = get_db_connection()
    try:
        rows = (
            db.query(SystemMetric)
            .order_by(SystemMetric.id.desc())
            .limit(50)
            .all()
        )
        return [
            {
                "id": m.id,
                "health_score": m.health_score,
                "drift_score": m.drift_score,
                "drift_detected": m.drift_detected,
                "grad_norm": m.grad_norm,
                "current_lr": m.current_lr,
                "recorded_at": m.recorded_at.isoformat() if m.recorded_at else None,
            }
            for m in rows
        ]
    finally:
        db.close()


@app.get("/health")
async def health_check():
    """Liveness / readiness probe for Railway."""
    db = get_db_connection()
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"
    finally:
        db.close()

    return {"status": "ok", "db": db_status, "version": "v5"}
