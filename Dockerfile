# Use Python 3.11 slim image
FROM python:3.11-slim

# Install system dependencies including timezone and build essentials
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Set timezone to Asia/Kolkata
ENV TZ=Asia/Kolkata
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install uv for fast package installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency definition
COPY pyproject.toml README.md /app/

# Install dependencies using uv (without installing the project itself yet)
RUN uv pip install --system -r pyproject.toml

# Copy project files
COPY indian_alpha /app/indian_alpha/

# Create persistent state directory structures
RUN mkdir -p /app/state/snapshots /app/state/history

# Expose Streamlit port
EXPOSE 8501

# Default environment variables
ENV PYTHONUNBUFFERED=1
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_THEME_BASE=dark

# The actual entrypoint is overridden in docker-compose.yml or Railway service config.
CMD ["python", "-m", "indian_alpha.run"]
