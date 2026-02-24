"""
Model Registry – version management backed by PostgreSQL model_registry table.
"""

import os

import torch
from sqlalchemy import func as sqla_func

from backend.config import MODEL_DIR
from backend.database import (
    get_db_connection,
    ModelRegistry as ModelRegistryRow,
    HealingEvent,
)
from backend.model import NeuralCollaborativeFiltering


class ModelRegistry:
    """CRUD operations on the model_registry table + model file I/O."""

    # ── Save ─────────────────────────────────────────────────────────────
    @staticmethod
    def save_version(model: NeuralCollaborativeFiltering, metadata: dict) -> int:
        """
        Persist a trained model to disk and register it in PostgreSQL.

        Parameters
        ----------
        model    : the trained PyTorch model
        metadata : dict with optional keys: health_score, train_loss, val_loss

        Returns
        -------
        int – the new version number
        """
        db = get_db_connection()
        try:
            # Next version = MAX(version) + 1 (or 1 if table is empty)
            max_ver = db.query(sqla_func.max(ModelRegistryRow.version)).scalar()
            version = (max_ver or 0) + 1

            # Save model file
            os.makedirs(MODEL_DIR, exist_ok=True)
            model_path = os.path.join(MODEL_DIR, f"model_v{version}.pt")
            torch.save(model.state_dict(), model_path)

            # Insert row
            row = ModelRegistryRow(
                version=version,
                health_score=metadata.get("health_score"),
                train_loss=metadata.get("train_loss"),
                val_loss=metadata.get("val_loss"),
                model_path=model_path,
                is_active=False,
            )
            db.add(row)
            db.commit()
            print(f"📦 Registered model v{version} → {model_path}")
            return version
        finally:
            db.close()

    # ── Load ─────────────────────────────────────────────────────────────
    @staticmethod
    def load_version(version: int) -> NeuralCollaborativeFiltering:
        """Load a model from disk by its registry version."""
        db = get_db_connection()
        try:
            row = (
                db.query(ModelRegistryRow)
                .filter(ModelRegistryRow.version == version)
                .first()
            )
            if row is None:
                raise ValueError(f"Version {version} not found in model_registry.")

            model = NeuralCollaborativeFiltering()
            model.load_state_dict(
                torch.load(row.model_path, map_location="cpu", weights_only=True)
            )
            model.eval()
            return model
        finally:
            db.close()

    # ── List ─────────────────────────────────────────────────────────────
    @staticmethod
    def get_all_versions() -> list[dict]:
        """Return all registered versions, newest first."""
        db = get_db_connection()
        try:
            rows = (
                db.query(ModelRegistryRow)
                .order_by(ModelRegistryRow.version.desc())
                .all()
            )
            return [
                {
                    "version": r.version,
                    "health_score": r.health_score,
                    "train_loss": r.train_loss,
                    "val_loss": r.val_loss,
                    "is_active": r.is_active,
                    "model_path": r.model_path,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]
        finally:
            db.close()

    # ── Activate ─────────────────────────────────────────────────────────
    @staticmethod
    def set_active(version: int):
        """Mark a single version as active (deactivate all others)."""
        db = get_db_connection()
        try:
            db.query(ModelRegistryRow).update({ModelRegistryRow.is_active: False})
            db.query(ModelRegistryRow).filter(
                ModelRegistryRow.version == version
            ).update({ModelRegistryRow.is_active: True})
            db.commit()
            print(f"✅ Model v{version} is now active.")
        finally:
            db.close()

    # ── Get Active ───────────────────────────────────────────────────────
    @staticmethod
    def get_active_version() -> dict | None:
        """Return the currently active model version, or None."""
        db = get_db_connection()
        try:
            row = (
                db.query(ModelRegistryRow)
                .filter(ModelRegistryRow.is_active == True)  # noqa: E712
                .first()
            )
            if row is None:
                return None
            return {
                "version": row.version,
                "health_score": row.health_score,
                "train_loss": row.train_loss,
                "val_loss": row.val_loss,
                "is_active": row.is_active,
                "model_path": row.model_path,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        finally:
            db.close()

    # ── Rollback ─────────────────────────────────────────────────────────
    @staticmethod
    def rollback() -> dict:
        """
        Roll back to the previous model version (N → N-1).
        Returns {"rolled_back_to": N-1, "previous_version": N}.
        """
        db = get_db_connection()
        try:
            # Current active version
            active = (
                db.query(ModelRegistryRow)
                .filter(ModelRegistryRow.is_active == True)  # noqa: E712
                .first()
            )
            if active is None:
                raise ValueError("No active model version to roll back from.")

            current_ver = active.version
            prev_ver = current_ver - 1

            # Check previous version exists
            prev_row = (
                db.query(ModelRegistryRow)
                .filter(ModelRegistryRow.version == prev_ver)
                .first()
            )
            if prev_row is None:
                raise ValueError(
                    f"Cannot rollback: version {prev_ver} does not exist."
                )

            # Deactivate all, activate previous
            db.query(ModelRegistryRow).update({ModelRegistryRow.is_active: False})
            db.query(ModelRegistryRow).filter(
                ModelRegistryRow.version == prev_ver
            ).update({ModelRegistryRow.is_active: True})

            # Log healing event
            db.add(HealingEvent(
                event_type="rollback",
                description=f"Rolled back from v{current_ver} to v{prev_ver}",
                old_version=current_ver,
                new_version=prev_ver,
                action_taken=f"Rolled back to v{prev_ver}",
            ))
            db.commit()

            print(f"⏪ Rolled back: v{current_ver} → v{prev_ver}")
            return {"rolled_back_to": prev_ver, "previous_version": current_ver}
        finally:
            db.close()
