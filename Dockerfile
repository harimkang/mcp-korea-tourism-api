# syntax=docker/dockerfile:1

# Use the Python version confirmed from .python-version
FROM python:3.12-slim

# Install uv
# --no-cache-dir reduces image size
RUN pip install --no-cache-dir uv

# Set the working directory in the container
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv based on the lock file
# The --system flag installs packages into the system Python, not a virtual environment
# --frozen ensures that the exact versions from the lock file are used
RUN uv sync --frozen

# Copy the rest of the application source code
COPY . .

# Set the API key as an environment variable
# IMPORTANT: It's strongly recommended to pass the API key securely at build time
# using --build-arg or at runtime using -e, rather than hardcoding it here.
# Example using build-arg:
# ARG KOREA_TOURISM_API_KEY_ARG
# ENV KOREA_TOURISM_API_KEY=${KOREA_TOURISM_API_KEY_ARG}
# Uncomment and replace the line below ONLY if you understand the security implications
# or for temporary local testing.
# ENV KOREA_TOURISM_API_KEY="YOUR_ACTUAL_API_KEY"

# Expose the port the MCP server might run on (if applicable)
# Adjust the port number if your server uses a different one.
# EXPOSE 8000

# Command to run the application
# Assumes uv run is executed from the project root (/app in the container)
CMD ["uv", "run", "-m", "mcp_tourism.server"] 