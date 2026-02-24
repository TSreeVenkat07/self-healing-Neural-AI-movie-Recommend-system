"""
Training pipeline – loads data from PostgreSQL, trains NCF, persists model.
Phase 2: gradient explosion detection, LR healing events, system metrics.
"""

import math
import os
import time

import torch
import torch.nn as nn
from torch.optim.lr_scheduler import ReduceLROnPlateau

from backend.config import (
    EPOCHS,
    LR,
    GRAD_CLIP_THRESHOLD,
    EXPLODING_GRAD_THRESHOLD,
    MODEL_DIR,
    LR_PATIENCE,
    LR_DECAY_FACTOR,
    MIN_LR,
)
from backend.data import get_dataloader_from_db
from backend.database import get_db_connection, HealingEvent, SystemMetric
from backend.model import NeuralCollaborativeFiltering


def _record_healing_event(db, *, event_type: str, description: str, action_taken: str):
    """Insert a row into the healing_events table."""
    db.add(HealingEvent(
        event_type=event_type,
        description=description,
        action_taken=action_taken,
    ))
    db.commit()


def _record_system_metric(db, *, health_score: float, grad_norm: float, current_lr: float):
    """Insert a row into the system_metrics table."""
    db.add(SystemMetric(
        health_score=health_score,
        grad_norm=grad_norm,
        current_lr=current_lr,
        drift_score=0.0,
        drift_detected=False,
    ))
    db.commit()


def train_model(drifted: bool = False) -> dict:
    """
    End-to-end training run with self-healing capabilities.

    Returns
    -------
    dict with keys: train_losses, val_losses, grad_norms,
                    lr_history, model_path, final_val_loss,
                    healing_events
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    db = get_db_connection()

    try:
        # ── Data ─────────────────────────────────────────────────────────
        dataloader = get_dataloader_from_db(drifted=drifted)

        # Split into train / val  (80/20)
        dataset = dataloader.dataset
        total = len(dataset)
        train_size = int(0.8 * total)
        val_size = total - train_size
        train_ds, val_ds = torch.utils.data.random_split(dataset, [train_size, val_size])

        train_loader = torch.utils.data.DataLoader(
            train_ds, batch_size=dataloader.batch_size, shuffle=True
        )
        val_loader = torch.utils.data.DataLoader(
            val_ds, batch_size=dataloader.batch_size, shuffle=False
        )

        # ── Model / Optimiser / Scheduler ────────────────────────────────
        model = NeuralCollaborativeFiltering().to(device)
        criterion = nn.MSELoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=LR)
        scheduler = ReduceLROnPlateau(
            optimizer,
            mode="min",
            patience=LR_PATIENCE,
            factor=LR_DECAY_FACTOR,
            min_lr=MIN_LR,
        )

        # ── Tracking ─────────────────────────────────────────────────────
        train_losses: list[float] = []
        val_losses: list[float] = []
        grad_norms: list[float] = []
        lr_history: list[float] = []

        # ── Training loop ────────────────────────────────────────────────
        for epoch in range(1, EPOCHS + 1):
            model.train()
            epoch_loss = 0.0
            epoch_grad_norm = 0.0
            n_batches = 0

            for user_ids, item_ids, ratings in train_loader:
                user_ids = user_ids.to(device)
                item_ids = item_ids.to(device)
                ratings = ratings.to(device)

                optimizer.zero_grad()
                preds = model(user_ids, item_ids)
                loss = criterion(preds, ratings)
                loss.backward()

                # ── Phase 2: Gradient monitoring ─────────────────────────
                total_norm = math.sqrt(
                    sum(p.grad.norm().item() ** 2 for p in model.parameters() if p.grad is not None)
                )

                if total_norm > EXPLODING_GRAD_THRESHOLD:
                    print(
                        f"⚠️  GRADIENT EXPLOSION at epoch {epoch}, "
                        f"norm={total_norm:.2f}"
                    )
                    torch.nn.utils.clip_grad_norm_(
                        model.parameters(), GRAD_CLIP_THRESHOLD
                    )
                    _record_healing_event(
                        db,
                        event_type="gradient_explosion",
                        description=f"Grad norm {total_norm:.2f} exceeded threshold",
                        action_taken="gradient_clipped",
                    )
                else:
                    # Normal gradient clipping (still applied)
                    torch.nn.utils.clip_grad_norm_(
                        model.parameters(), GRAD_CLIP_THRESHOLD
                    )

                epoch_grad_norm += total_norm
                optimizer.step()
                epoch_loss += loss.item()
                n_batches += 1

            avg_train_loss = epoch_loss / max(n_batches, 1)
            avg_grad_norm = epoch_grad_norm / max(n_batches, 1)

            # ── Validation ───────────────────────────────────────────────
            model.eval()
            val_loss = 0.0
            val_batches = 0
            with torch.no_grad():
                for user_ids, item_ids, ratings in val_loader:
                    user_ids = user_ids.to(device)
                    item_ids = item_ids.to(device)
                    ratings = ratings.to(device)
                    preds = model(user_ids, item_ids)
                    val_loss += criterion(preds, ratings).item()
                    val_batches += 1

            avg_val_loss = val_loss / max(val_batches, 1)

            # ── Phase 2: LR adaptation healing ───────────────────────────
            old_lr = optimizer.param_groups[0]["lr"]
            scheduler.step(avg_val_loss)
            new_lr = optimizer.param_groups[0]["lr"]

            if new_lr < old_lr:
                print(f"🔧 LR reduced: {old_lr:.6f} → {new_lr:.6f}")
                _record_healing_event(
                    db,
                    event_type="lr_reduction",
                    description=f"LR reduced to {new_lr:.6f}",
                    action_taken="lr_adapted",
                )

            # ── Phase 2: System metrics recording ────────────────────────
            health_score = max(0.0, 1.0 - avg_val_loss)
            _record_system_metric(
                db,
                health_score=health_score,
                grad_norm=avg_grad_norm,
                current_lr=new_lr,
            )

            train_losses.append(avg_train_loss)
            val_losses.append(avg_val_loss)
            grad_norms.append(avg_grad_norm)
            lr_history.append(new_lr)

            print(
                f"Epoch {epoch}/{EPOCHS}  "
                f"train_loss={avg_train_loss:.4f}  "
                f"val_loss={avg_val_loss:.4f}  "
                f"grad_norm={avg_grad_norm:.4f}  "
                f"lr={new_lr:.6f}  "
                f"health={health_score:.4f}"
            )

        # ── Persist model ────────────────────────────────────────────────
        os.makedirs(MODEL_DIR, exist_ok=True)
        timestamp = int(time.time())
        model_path = os.path.join(MODEL_DIR, f"model_v{timestamp}.pt")
        torch.save(model.state_dict(), model_path)
        print(f"✅ Model saved → {model_path}")

        # ── Fetch healing events from DB ─────────────────────────────────
        healing_rows = db.query(HealingEvent).order_by(HealingEvent.id.desc()).limit(50).all()
        healing_events = [
            {
                "event_type": h.event_type,
                "description": h.description,
                "action_taken": h.action_taken,
                "created_at": h.created_at.isoformat() if h.created_at else None,
            }
            for h in healing_rows
        ]

        return {
            "train_losses": train_losses,
            "val_losses": val_losses,
            "grad_norms": grad_norms,
            "lr_history": lr_history,
            "healing_events": healing_events,
            "model_path": model_path,
            "final_val_loss": val_losses[-1] if val_losses else None,
        }

    finally:
        db.close()
