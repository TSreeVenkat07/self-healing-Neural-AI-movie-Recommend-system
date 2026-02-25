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

20: If you are experiencing Memory limits (`OOM`) or NumPy `_ARRAY_API not found` errors during deployment:
21: 1. Go to your Render Dashboard for the `recsys-backend` Web Service.
22: 2. Click **Manual Deploy** and select **"Clear build cache & deploy"**.
23: 3. We have pinned `numpy==1.26.4` and added memory-reducing Docker thread limits to `Dockerfile` to prevent these errors on free instances.
24: 
25: ## Backend Deployment via Google Colab
26: 
27: Due to the high memory requirements of training the PyTorch models, the backend is now hosted computationally on Google Colab, leveraging a free GPU instance, and connected securely via Ngrok.
28: 
29: To run the backend:
30: 1. Open the [Backend Colab Notebook](colab/) (drop your `.ipynb` file in the `colab/` folder).
31: 2. Upload the `data/` and `models/` folders to your Colab workspace.
32: 3. Add your `NGROK_AUTH_TOKEN` and run all cells.
33: 4. Copy the generated `ngrok` public URL and update your React frontend `VITE_API_URL` variable in `.env`.
34: 
35: Note: The PostgreSQL Database is still hosted entirely on Render.
