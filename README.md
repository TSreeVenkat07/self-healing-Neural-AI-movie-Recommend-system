# Self-Healing Neural Recommendation System

A self-healing movie recommendation engine featuring drift-detection and automatic neural-network model retraining.

## Technology Stack

**Backend System**
* **Core:** Python (Data/Models), FastAPI (REST API), Uvicorn (ASGI Server)
* **Databases:** PostgreSQL (Relational Data & Registry), SQLAlchemy (ORM)
* **Machine Learning:** PyTorch (Neural Collaborative Filtering)
* **Data Ops:** Pandas (Transformations), NumPy (Matrix Ops)

**Frontend Dashboard**
* **Framework:** React 19, Vite (Build Tool)
* **Styling:** Tailwind CSS v4 
* **Visualizations:** Recharts (React Charting)

## Deployment to Render

If you are experiencing Memory limits (`OOM`) or NumPy `_ARRAY_API not found` errors during deployment:
1. Go to your Render Dashboard for the `recsys-backend` Web Service.
2. Click **Manual Deploy** and select **"Clear build cache & deploy"**.
3. We have pinned `numpy==1.26.4` and added memory-reducing Docker thread limits to `Dockerfile` to prevent these errors on free instances.
