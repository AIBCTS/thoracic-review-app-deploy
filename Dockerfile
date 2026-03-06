# Use a stable Python base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install minimal system dependencies (only if absolutely needed)
# Added retries and fixed mirror issues by using a simpler approach
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Healthcheck
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Start command
ENTRYPOINT ["streamlit", "run", "review_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
