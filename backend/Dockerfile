# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
# - tesseract-ocr: for Image OCR
# - libgl1-mesa-glx: for OpenCV
# - ffmpeg: for Audio/Video processing
# - libmagic1: for file type detection
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1-mesa-glx \
    ffmpeg \
    libmagic1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Render uses PORT env var, but we expose 8000 for local)
EXPOSE 8000

# Run the initialization script and then the server
CMD ["sh", "-c", "python -m app.db.init_db && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
