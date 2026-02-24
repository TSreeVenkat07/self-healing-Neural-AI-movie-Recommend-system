"""
MovieLens 1M data pipeline – download, parse, seed PostgreSQL, build DataLoaders.

Dataset: MovieLens 1M  (1 million ratings, 6,040 users, 3,952 movies)
Source:  https://files.grouplens.org/datasets/movielens/ml-1m.zip

Drift simulation uses a timestamp split: ratings before the midpoint are
"normal" and ratings after the midpoint represent concept drift.
"""

import io
import os
import zipfile

import pandas as pd
import requests
import torch
from torch.utils.data import DataLoader, TensorDataset

from backend.config import (
    BATCH_SIZE,
    DATA_DIR,
    DRIFT_TIMESTAMP_SPLIT,
    MOVIELENS_URL,
)
from backend.database import get_db_connection, Interaction, Movie

# ──────────────────────────── item_id ↔ movie_id map ─────────────────────
# When we remap IDs to 0-based contiguous indices for training, we keep a
# mapping so recommendations (item_id) can be resolved to movie metadata.
_item_to_movie: dict[int, int] = {}   # populated by _download_movielens()


def load_item_mapping():
    """Load the mapping into memory if the CSV exists."""
    map_path = os.path.join(DATA_DIR, "item_map.csv")
    if os.path.exists(map_path):
        mp = pd.read_csv(map_path)
        _item_to_movie.clear()
        _item_to_movie.update(dict(zip(mp["item_id"], mp["original_id"])))

# ──────────────────────────── Download & Parse ───────────────────────────
def _download_movielens() -> pd.DataFrame:
    """
    Download MovieLens 1M zip, extract ratings.dat, return a DataFrame.
    Caches the parsed CSV locally so subsequent runs are instant.
    """
    global _item_to_movie
    os.makedirs(DATA_DIR, exist_ok=True)
    cache_path = os.path.join(DATA_DIR, "ratings.csv")
    map_path = os.path.join(DATA_DIR, "item_map.csv")

    if os.path.exists(cache_path) and os.path.exists(map_path):
        print("📂 Loading cached MovieLens 1M ratings …")
        df = pd.read_csv(cache_path)
        load_item_mapping()
        return df

    print("⬇️  Downloading MovieLens 1M dataset …")
    resp = requests.get(MOVIELENS_URL, timeout=120)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        with zf.open("ml-1m/ratings.dat") as f:
            df = pd.read_csv(
                f,
                sep="::",
                header=None,
                names=["user_id", "item_id", "rating", "timestamp"],
                engine="python",
                encoding="latin-1",
            )

    # Re-map IDs to 0-based contiguous indices
    df["user_id"] = df["user_id"].astype("category").cat.codes

    item_cat = df["item_id"].astype("category")
    original_ids = item_cat.cat.categories.tolist()
    df["item_id"] = item_cat.cat.codes
    df["rating"] = df["rating"].astype(float)

    # Save item_id → original movie_id mapping
    map_df = pd.DataFrame({
        "item_id": range(len(original_ids)),
        "original_id": original_ids,
    })
    map_df.to_csv(map_path, index=False)
    _item_to_movie.clear()
    _item_to_movie.update(dict(zip(map_df["item_id"], map_df["original_id"])))

    df.to_csv(cache_path, index=False)
    print(f"✅ MovieLens 1M: {len(df):,} ratings, "
          f"{df['user_id'].nunique()} users, {df['item_id'].nunique()} items")
    return df


def _parse_movies() -> pd.DataFrame:
    """Parse movies.dat from cached zip or re-download."""
    os.makedirs(DATA_DIR, exist_ok=True)
    cache_path = os.path.join(DATA_DIR, "movies.csv")

    if os.path.exists(cache_path):
        return pd.read_csv(cache_path)

    print("🎬 Parsing MovieLens 1M movies …")
    zip_path = None
    # Try to download if not already cached as ratings
    resp = requests.get(MOVIELENS_URL, timeout=120)
    resp.raise_for_status()

    movies = []
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        with zf.open("ml-1m/movies.dat") as f:
            for line in f:
                line = line.decode("latin-1").strip()
                parts = line.split("::")
                if len(parts) >= 3:
                    mid = int(parts[0])
                    raw_title = parts[1].strip()
                    genres = parts[2].strip()
                    # Extract year from title like "Toy Story (1995)"
                    year = None
                    title = raw_title
                    if raw_title.endswith(")") and "(" in raw_title:
                        try:
                            year = int(raw_title[raw_title.rfind("(") + 1:raw_title.rfind(")")])
                            title = raw_title[:raw_title.rfind("(")].strip()
                        except ValueError:
                            pass
                    movies.append({
                        "movie_id": mid,
                        "title": title,
                        "year": year,
                        "genres": genres,
                    })

    df = pd.DataFrame(movies)
    df.to_csv(cache_path, index=False)
    print(f"✅ Parsed {len(df)} movies.")
    return df


def _split_by_drift(df: pd.DataFrame):
    """
    Split the DataFrame into normal and drifted subsets using the
    DRIFT_TIMESTAMP_SPLIT threshold.
    """
    normal = df[df["timestamp"] < DRIFT_TIMESTAMP_SPLIT].copy()
    drifted = df[df["timestamp"] >= DRIFT_TIMESTAMP_SPLIT].copy()
    return normal, drifted


# ──────────────────────────── Seeding ────────────────────────────────────
def seed_movies():
    """Parse movies.dat and seed the movies table."""
    db = get_db_connection()
    try:
        existing = db.query(Movie).limit(1).first()
        if existing:
            print("⏭️  Movies already seeded — skipping.")
            return
        df = _parse_movies()
        rows = [
            Movie(
                movie_id=int(row.movie_id),
                title=str(row.title),
                year=int(row.year) if pd.notna(row.year) else None,
                genres=str(row.genres) if pd.notna(row.genres) else "",
            )
            for row in df.itertuples(index=False)
        ]
        db.bulk_save_objects(rows)
        db.commit()
        print(f"✅ Seeded {len(rows)} movies.")
    finally:
        db.close()


def seed_database(drifted: bool = False):
    """
    Download MovieLens 1M (if needed), split by timestamp, and bulk-insert
    the chosen subset into the PostgreSQL `interactions` table.
    """
    db = get_db_connection()
    try:
        existing = (
            db.query(Interaction)
            .filter(Interaction.is_drifted == drifted)
            .limit(1)
            .first()
        )
        if existing:
            print(f"⏭️  Interactions (drifted={drifted}) already seeded — skipping.")
            return

        df = _download_movielens()
        normal, drifted_df = _split_by_drift(df)
        subset = drifted_df if drifted else normal

        rows = [
            Interaction(
                user_id=int(row.user_id),
                item_id=int(row.item_id),
                rating=float(row.rating),
                is_drifted=drifted,
            )
            for row in subset.itertuples(index=False)
        ]
        db.bulk_save_objects(rows)
        db.commit()
        print(f"✅ Seeded {len(rows):,} MovieLens interactions (drifted={drifted}).")
    finally:
        db.close()


# ──────────────────────────── DataLoader ─────────────────────────────────
def get_dataloader_from_db(drifted: bool = False) -> DataLoader:
    """
    Fetch interactions from PostgreSQL and return a PyTorch DataLoader.
    """
    db = get_db_connection()
    try:
        rows = (
            db.query(Interaction)
            .filter(Interaction.is_drifted == drifted)
            .all()
        )
    finally:
        db.close()

    if not rows:
        raise ValueError(
            f"No interactions found with is_drifted={drifted}. "
            "Did you seed the database?"
        )

    user_ids = torch.tensor([r.user_id for r in rows], dtype=torch.long)
    item_ids = torch.tensor([r.item_id for r in rows], dtype=torch.long)
    ratings = torch.tensor([r.rating for r in rows], dtype=torch.float32) / 5.0  # normalise to [0,1]

    dataset = TensorDataset(user_ids, item_ids, ratings)
    return DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)
