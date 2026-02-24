# Use an official lightweight Python image
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Upgrade pip and install dependencies first to leverage Docker cache
COPY requirements.txt .

# Install dependencies (no-cache-dir keeps the image size small)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the Railway port
EXPOSE 8000

# Start the FastAPI application
CMD sh -c "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"
