FROM python:3.13-slim

WORKDIR /app

# Install uv for fast package management
RUN pip install uv

# Copy dependency files first for caching
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen

# Copy the whole project
COPY . .

# By default, keep the container running or override in compose
CMD ["uv", "run", "python", "-m", "src.apps.feedback_server"]
