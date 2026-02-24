"""
Healing Controller – monitors model health and triggers self-healing.
"""

import threading
import time

from backend.config import HEALTH_THRESHOLD
from backend.database import get_db_connection, HealingEvent, SystemMetric
from backend.model import NeuralCollaborativeFiltering
from backend.registry import ModelRegistry
from backend.train import train_model


def _compute_health_score() -> float:
    """
    Compute current model health from the latest system_metrics row.
    Returns 0.0 if no metrics exist yet.
    """
    db = get_db_connection()
    try:
        latest = (
            db.query(SystemMetric)
            .order_by(SystemMetric.id.desc())
            .first()
        )
        return latest.health_score if latest else 0.0
    finally:
        db.close()


class HealingController:
    """Orchestrates automated model healing cycles."""

    def __init__(self):
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    # ── Single healing cycle ─────────────────────────────────────────────
    def run_healing_cycle(self) -> dict:
        """
        1. Check current health score
        2. If healthy → no action
        3. If unhealthy → retrain on drifted data, evaluate, deploy or reject
        """
        current_score = _compute_health_score()

        # Log score to system_metrics
        db = get_db_connection()
        try:
            db.add(SystemMetric(
                health_score=current_score,
                drift_score=0.0,
                drift_detected=current_score < HEALTH_THRESHOLD,
                grad_norm=0.0,
                current_lr=0.0,
            ))
            db.commit()
        finally:
            db.close()

        # ── Healthy? ─────────────────────────────────────────────────────
        if current_score >= HEALTH_THRESHOLD:
            return {
                "action": "none",
                "reason": "healthy",
                "score": current_score,
            }

        # ── Unhealthy → trigger healing ──────────────────────────────────
        db = get_db_connection()
        try:
            db.add(HealingEvent(
                event_type="healing_triggered",
                description=f"Score {current_score:.4f} below threshold {HEALTH_THRESHOLD}",
                old_score=current_score,
                action_taken="healing_initiated",
            ))
            db.commit()
        finally:
            db.close()

        print(f"🩺 Healing triggered — score {current_score:.4f} < {HEALTH_THRESHOLD}")

        # ── Retrain on drifted data ──────────────────────────────────────
        result = train_model(drifted=True)
        new_score = max(0.0, 1.0 - result["final_val_loss"]) if result["final_val_loss"] is not None else 0.0

        # ── Evaluate: deploy or reject ───────────────────────────────────
        if new_score > current_score:
            # Load the freshly trained model and register it
            import torch
            model = NeuralCollaborativeFiltering()
            model.load_state_dict(
                torch.load(result["model_path"], map_location="cpu", weights_only=True)
            )
            model.eval()

            new_version = ModelRegistry.save_version(model, {
                "health_score": new_score,
                "train_loss": result["train_losses"][-1] if result["train_losses"] else None,
                "val_loss": result["final_val_loss"],
            })
            ModelRegistry.set_active(new_version)

            db = get_db_connection()
            try:
                db.add(HealingEvent(
                    event_type="model_deployed",
                    description=f"New model v{new_version} deployed after healing",
                    old_score=current_score,
                    new_score=new_score,
                    new_version=new_version,
                    action_taken=f"Deployed v{new_version}",
                ))
                db.commit()
            finally:
                db.close()

            print(f"✅ Healed → deployed v{new_version} (score {current_score:.4f} → {new_score:.4f})")
            return {
                "action": "deployed",
                "old_score": current_score,
                "new_score": new_score,
                "version": new_version,
            }
        else:
            db = get_db_connection()
            try:
                db.add(HealingEvent(
                    event_type="healing_rejected",
                    description="New model underperformed current model",
                    old_score=current_score,
                    new_score=new_score,
                    action_taken="kept_current",
                ))
                db.commit()
            finally:
                db.close()

            print(f"❌ Healing rejected — new score {new_score:.4f} ≤ current {current_score:.4f}")
            return {
                "action": "rejected",
                "reason": "new model underperformed",
                "old_score": current_score,
                "new_score": new_score,
            }

    # ── Auto-healing background thread ───────────────────────────────────
    def start_auto_healing(self, interval_seconds: int = 60):
        """Start a background thread that runs healing cycles periodically."""
        if self._thread and self._thread.is_alive():
            return {"status": "already_running"}

        self._stop_event.clear()

        def _loop():
            while not self._stop_event.is_set():
                try:
                    report = self.run_healing_cycle()
                    print(f"🔄 Auto-heal cycle complete: {report.get('action')}")
                except Exception as e:
                    print(f"⚠️  Auto-heal error: {e}")
                self._stop_event.wait(timeout=interval_seconds)

        self._thread = threading.Thread(target=_loop, daemon=True, name="auto-healer")
        self._thread.start()
        print(f"🚀 Auto-healing started (every {interval_seconds}s)")
        return {"status": "started", "interval_seconds": interval_seconds}

    def stop_auto_healing(self):
        """Signal the background healing thread to stop."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        print("🛑 Auto-healing stopped.")
        return {"status": "stopped"}
