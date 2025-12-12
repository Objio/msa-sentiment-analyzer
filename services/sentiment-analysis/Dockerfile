# Multi-stage build for Sentiment Analysis Service
FROM python:3.11-slim as builder

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages
COPY --from=builder /root/.local /root/.local

# Copy shared libraries
COPY shared/ ./shared/

# Copy service code
COPY services/sentiment-analysis/ ./services/sentiment-analysis/

# Set PATH
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/app

# Run the worker
CMD ["python", "services/sentiment-analysis/main.py"]
