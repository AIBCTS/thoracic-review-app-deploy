# Use a stable Python base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# No system dependencies needed for this app.
# Create results directory
RUN mkdir -p results

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Start command - Using JSON array format (exec form) for better signal handling
CMD ["streamlit", "run", "review_app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
