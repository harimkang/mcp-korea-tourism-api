# syntax=docker/dockerfile:1

# Use the Python version confirmed from .python-version
FROM python:3.12-slim

# Install uv
# --no-cache-dir reduces image size
RUN pip install --no-cache-dir uv

# Set the working directory in the container
WORKDIR /app

# Copy dependency files first to leverage Docker cache
COPY pyproject.toml uv.lock ./

# Install dependencies using uv based on the lock file
# The --system flag is not needed/valid for uv sync
# --frozen ensures that the exact versions from the lock file are used
RUN uv sync --frozen

# Copy the rest of the application source code (including the src directory)
COPY . .

# Install the project itself from the src directory
# This makes the mcp_tourism package available to the Python interpreter
# --no-deps prevents reinstalling already synced dependencies
RUN uv pip install . --no-deps

# Set the API key as an environment variable
# IMPORTANT: It's strongly recommended to pass the API key securely at runtime using -e.
# Example runtime command: docker run -e KOREA_TOURISM_API_KEY="YOUR_ACTUAL_API_KEY" ...
# ENV KOREA_TOURISM_API_KEY="YOUR_ACTUAL_API_KEY" # Avoid hardcoding if possible

# Expose the port the MCP server might run on (if applicable)
# Adjust the port number if your server uses a different one.
# EXPOSE 8000

# Command to run the application
# Python can now find the module thanks to the install step above
CMD ["uv", "run", "-m", "mcp_tourism.server"] 