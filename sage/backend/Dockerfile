FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy application code first (needed for editable install)
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Create non-root user
RUN useradd -m -u 1000 sage && chown -R sage:sage /app
USER sage

EXPOSE 8000

CMD ["uvicorn", "sage.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
