"""
Neural Collaborative Filtering model.
"""

import torch
import torch.nn as nn

from backend.config import NUM_USERS, NUM_ITEMS, EMBED_DIM


class NeuralCollaborativeFiltering(nn.Module):
    """
    Embedding-based collaborative filtering with fully-connected layers.

    Architecture
    ────────────
    User embedding  (NUM_USERS × EMBED_DIM)  ─┐
                                               ├─ concat → 128 → 64 → 32 → 1 → sigmoid
    Item embedding  (NUM_ITEMS × EMBED_DIM)  ─┘
    """

    def __init__(self):
        super().__init__()

        self.user_embedding = nn.Embedding(NUM_USERS, EMBED_DIM)
        self.item_embedding = nn.Embedding(NUM_ITEMS, EMBED_DIM)

        self.fc = nn.Sequential(
            nn.Linear(EMBED_DIM * 2, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid(),
        )

    def forward(self, user_ids: torch.Tensor, item_ids: torch.Tensor) -> torch.Tensor:
        user_emb = self.user_embedding(user_ids)   # (B, EMBED_DIM)
        item_emb = self.item_embedding(item_ids)   # (B, EMBED_DIM)
        x = torch.cat([user_emb, item_emb], dim=-1)  # (B, EMBED_DIM*2)
        return self.fc(x).squeeze(-1)               # (B,)
