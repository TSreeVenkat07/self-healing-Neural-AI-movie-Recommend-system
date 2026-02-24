import os

# ──────────────────────────── Data Dimensions ────────────────────────────
# MovieLens 1M: 6,040 users × 3,952 movies  (IDs are re-mapped to 0-based)
NUM_USERS = 6_040
NUM_ITEMS = 3_952
EMBED_DIM = 64

# ──────────────────────────── Training Hyperparameters ────────────────────
EPOCHS = 10
LR = 0.001
BATCH_SIZE = 256

# ──────────────────────────── Self-Healing Thresholds ────────────────────
HEALTH_THRESHOLD = 0.7
GRAD_CLIP_THRESHOLD = 1.0
EXPLODING_GRAD_THRESHOLD = 10.0

# ──────────────────────────── LR Scheduling ──────────────────────────────
LR_PATIENCE = 3
LR_DECAY_FACTOR = 0.5
MIN_LR = 1e-6

# ──────────────────────────── Paths & Database ───────────────────────────
MODEL_DIR = "/models"  # Railway persistent volume path
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
MOVIELENS_URL = "https://files.grouplens.org/datasets/movielens/ml-1m.zip"
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:1234@localhost/recsys")

# ──────────────────────────── Drift Simulation ───────────────────────────
# Timestamp split: ratings before this are "normal", after are "drifted"
# MovieLens 1M timestamps range ~2000-04 to 2003-02
# Midpoint ≈ 978,300,000 (roughly Jan 2001)
DRIFT_TIMESTAMP_SPLIT = 978_300_000
