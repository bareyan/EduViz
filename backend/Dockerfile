FROM python:3.11-slim

# Install system dependencies (optimized texlive packages)
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    ffmpeg \
    texlive-base \
    texlive-latex-extra \
    texlive-fonts-recommended \
    texlive-fonts-extra \
    libcairo2-dev \
    libpango1.0-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user and set up directories with proper permissions
RUN useradd -m -u 1000 appuser && \
    mkdir -p uploads outputs job_data logs && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check - increased start period for texlive initialization
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
