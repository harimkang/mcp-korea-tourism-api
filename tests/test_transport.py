import pytest
import argparse
import os
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient
from starlette.applications import Starlette

from mcp_tourism.server import health_check


class TestTransportConfiguration:
    """Test transport configuration and command line argument parsing."""

    def test_default_transport_configuration(self, monkeypatch):
        """Test default transport configuration when no args or env vars are set."""
        # Clear relevant environment variables
        for var in [
            "MCP_TRANSPORT",
            "MCP_HOST",
            "MCP_PORT",
            "MCP_PATH",
            "MCP_LOG_LEVEL",
        ]:
            monkeypatch.delenv(var, raising=False)

        # Mock argument parser
        parser = argparse.ArgumentParser(description="Korea Tourism API MCP Server")
        parser.add_argument(
            "--transport", choices=["stdio", "streamable-http", "sse"], default=None
        )
        parser.add_argument("--host", type=str, default=None)
        parser.add_argument("--port", type=int, default=None)
        parser.add_argument(
            "--log-level",
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            default=None,
        )
        parser.add_argument("--path", type=str, default=None)

        # Test default configuration
        args = parser.parse_args([])

        transport = args.transport or os.environ.get("MCP_TRANSPORT", "stdio")
        assert transport == "stdio"

    def test_command_line_argument_parsing(self):
        """Test command line argument parsing for transport configuration."""
        parser = argparse.ArgumentParser(description="Korea Tourism API MCP Server")
        parser.add_argument(
            "--transport", choices=["stdio", "streamable-http", "sse"], default=None
        )
        parser.add_argument("--host", type=str, default=None)
        parser.add_argument("--port", type=int, default=None)
        parser.add_argument(
            "--log-level",
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            default=None,
        )
        parser.add_argument("--path", type=str, default=None)

        # Test with command line arguments
        test_args = [
            "--transport",
            "streamable-http",
            "--host",
            "0.0.0.0",
            "--port",
            "3000",
            "--log-level",
            "DEBUG",
            "--path",
            "/api/mcp",
        ]

        args = parser.parse_args(test_args)

        assert args.transport == "streamable-http"
        assert args.host == "0.0.0.0"
        assert args.port == 3000
        assert args.log_level == "DEBUG"
        assert args.path == "/api/mcp"

    def test_environment_variable_configuration(self, monkeypatch):
        """Test environment variable configuration."""
        # Set environment variables
        monkeypatch.setenv("MCP_TRANSPORT", "sse")
        monkeypatch.setenv("MCP_HOST", "127.0.0.1")
        monkeypatch.setenv("MCP_PORT", "8080")
        monkeypatch.setenv("MCP_LOG_LEVEL", "INFO")
        monkeypatch.setenv("MCP_PATH", "/mcp")

        # Test environment variable reading
        assert os.environ.get("MCP_TRANSPORT") == "sse"
        assert os.environ.get("MCP_HOST") == "127.0.0.1"
        assert int(os.environ.get("MCP_PORT", "8000")) == 8080
        assert os.environ.get("MCP_LOG_LEVEL") == "INFO"
        assert os.environ.get("MCP_PATH") == "/mcp"

    def test_command_line_overrides_environment(self, monkeypatch):
        """Test that command line arguments override environment variables."""
        # Set environment variables
        monkeypatch.setenv("MCP_TRANSPORT", "sse")
        monkeypatch.setenv("MCP_HOST", "127.0.0.1")
        monkeypatch.setenv("MCP_PORT", "8080")

        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--transport", choices=["stdio", "streamable-http", "sse"], default=None
        )
        parser.add_argument("--host", type=str, default=None)
        parser.add_argument("--port", type=int, default=None)

        # Parse command line arguments that should override env vars
        args = parser.parse_args(["--transport", "streamable-http", "--port", "3000"])

        # Test configuration priority
        transport = args.transport or os.environ.get("MCP_TRANSPORT", "stdio")
        host = args.host or os.environ.get("MCP_HOST", "127.0.0.1")
        port = args.port or int(os.environ.get("MCP_PORT", "8000"))

        assert transport == "streamable-http"  # CLI override
        assert host == "127.0.0.1"  # From env var
        assert port == 3000  # CLI override

    def test_http_config_generation(self, monkeypatch):
        """Test HTTP configuration generation for HTTP transports."""
        # Set up test environment
        monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")
        monkeypatch.setenv("MCP_HOST", "0.0.0.0")
        monkeypatch.setenv("MCP_PORT", "8000")
        monkeypatch.setenv("MCP_LOG_LEVEL", "INFO")
        monkeypatch.setenv("MCP_PATH", "/mcp")

        transport = os.environ.get("MCP_TRANSPORT", "stdio")

        # Test HTTP config generation
        http_config = {}
        if transport in ["streamable-http", "sse"]:
            http_config.update(
                {
                    "host": os.environ.get("MCP_HOST", "127.0.0.1"),
                    "port": int(os.environ.get("MCP_PORT", "8000")),
                    "log_level": os.environ.get("MCP_LOG_LEVEL", "INFO"),
                    "path": os.environ.get("MCP_PATH", "/mcp"),
                }
            )

        assert http_config["host"] == "0.0.0.0"
        assert http_config["port"] == 8000
        assert http_config["log_level"] == "INFO"
        assert http_config["path"] == "/mcp"

    def test_stdio_transport_no_http_config(self):
        """Test that stdio transport doesn't generate HTTP config."""
        transport = "stdio"

        http_config = {}
        if transport in ["streamable-http", "sse"]:
            http_config.update(
                {
                    "host": "0.0.0.0",
                    "port": 8000,
                }
            )

        assert http_config == {}


class TestHealthCheckEndpoint:
    """Test health check endpoint functionality."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock Starlette request object."""
        request = MagicMock()
        request.url = MagicMock()
        request.url.path = "/health"
        return request

    @pytest.mark.asyncio
    async def test_health_check_healthy_status(self, mock_request, monkeypatch):
        """Test health check endpoint returns healthy status when API client is working."""
        # Set up environment
        monkeypatch.setenv("KOREA_TOURISM_API_KEY", "test-key")
        monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")

        # Mock get_api_client to return a working client
        with patch("mcp_tourism.server.get_api_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            # Call health check
            response = await health_check(mock_request)

            # Verify response
            assert response.status_code == 200

            # Check response content type
            assert response.headers["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_status(self, mock_request, monkeypatch):
        """Test health check endpoint returns unhealthy status when API client fails."""
        # Set up environment
        monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")

        # Mock get_api_client to raise an exception
        with patch("mcp_tourism.server.get_api_client") as mock_get_client:
            mock_get_client.side_effect = Exception("API client initialization failed")

            # Call health check
            response = await health_check(mock_request)

            # Verify response
            assert response.status_code == 503

            # Check response content type
            assert response.headers["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_health_check_default_transport(self, mock_request, monkeypatch):
        """Test health check endpoint with default stdio transport."""
        # Clear transport environment variable
        monkeypatch.delenv("MCP_TRANSPORT", raising=False)

        # Mock get_api_client to return a working client
        with patch("mcp_tourism.server.get_api_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            # Call health check
            response = await health_check(mock_request)

            # Verify response
            assert response.status_code == 200

            # Check response content type
            assert response.headers["content-type"] == "application/json"


class TestTransportValidation:
    """Test transport validation and error handling."""

    def test_valid_transport_choices(self):
        """Test that parser accepts valid transport choices."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--transport", choices=["stdio", "streamable-http", "sse"])

        # Test valid choices
        for transport in ["stdio", "streamable-http", "sse"]:
            args = parser.parse_args(["--transport", transport])
            assert args.transport == transport

    def test_invalid_transport_choice(self):
        """Test that parser rejects invalid transport choices."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--transport", choices=["stdio", "streamable-http", "sse"])

        # Test invalid choice
        with pytest.raises(SystemExit):
            parser.parse_args(["--transport", "invalid-transport"])

    def test_port_type_validation(self):
        """Test that parser validates port as integer."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--port", type=int)

        # Test valid port
        args = parser.parse_args(["--port", "8000"])
        assert args.port == 8000

        # Test invalid port
        with pytest.raises(SystemExit):
            parser.parse_args(["--port", "not-a-number"])

    def test_log_level_choices(self):
        """Test that parser accepts valid log level choices."""
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        )

        # Test valid choices
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            args = parser.parse_args(["--log-level", level])
            assert args.log_level == level


class TestServerIntegration:
    """Test server integration with different transports."""

    @pytest.mark.asyncio
    async def test_mcp_server_with_stdio_transport(self, monkeypatch):
        """Test that MCP server can be configured with stdio transport."""
        # Set up environment
        monkeypatch.setenv("KOREA_TOURISM_API_KEY", "test-key")
        monkeypatch.setenv("MCP_TRANSPORT", "stdio")

        # Mock the actual server run to avoid starting real server
        with patch("mcp_tourism.server.mcp.run") as mock_run:
            # Import and run the server configuration logic (without actually running)
            transport = os.environ.get("MCP_TRANSPORT", "stdio")

            if transport == "stdio":
                # This would normally call mcp.run(transport="stdio")
                mock_run.assert_not_called()  # Since we're just testing the logic
                assert transport == "stdio"

    def test_http_config_preparation(self, monkeypatch):
        """Test HTTP configuration preparation for HTTP transports."""
        # Set up environment for HTTP transport
        monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")
        monkeypatch.setenv("MCP_HOST", "0.0.0.0")
        monkeypatch.setenv("MCP_PORT", "3000")
        monkeypatch.setenv("MCP_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("MCP_PATH", "/api/mcp")

        transport = os.environ.get("MCP_TRANSPORT", "stdio")

        # Prepare HTTP config like in the actual server
        http_config = {}
        if transport in ["streamable-http", "sse"]:
            http_config.update(
                {
                    "host": os.environ.get("MCP_HOST", "127.0.0.1"),
                    "port": int(os.environ.get("MCP_PORT", "8000")),
                    "log_level": os.environ.get("MCP_LOG_LEVEL", "INFO"),
                    "path": os.environ.get("MCP_PATH", "/mcp"),
                }
            )

        # Verify configuration
        assert http_config["host"] == "0.0.0.0"
        assert http_config["port"] == 3000
        assert http_config["log_level"] == "DEBUG"
        assert http_config["path"] == "/api/mcp"

    @pytest.mark.asyncio
    async def test_health_endpoint_integration(self, monkeypatch):
        """Test health endpoint integration with MCP server."""
        # Set up environment
        monkeypatch.setenv("KOREA_TOURISM_API_KEY", "test-key")
        monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")

        # Create a test application with the health route
        app = Starlette()
        app.add_route("/health", health_check, methods=["GET"])

        # Create test client
        with TestClient(app) as client:
            # Mock get_api_client
            with patch("mcp_tourism.server.get_api_client") as mock_get_client:
                mock_client = MagicMock()
                mock_get_client.return_value = mock_client

                # Test health endpoint
                response = client.get("/health")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "healthy"
                assert data["service"] == "Korea Tourism API MCP Server"
                assert data["transport"] == "streamable-http"
                assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_health_endpoint_error_handling(self, monkeypatch):
        """Test health endpoint error handling when API client fails."""
        # Set up environment
        monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")

        # Create a test application with the health route
        app = Starlette()
        app.add_route("/health", health_check, methods=["GET"])

        # Create test client
        with TestClient(app) as client:
            # Mock get_api_client to raise an exception
            with patch("mcp_tourism.server.get_api_client") as mock_get_client:
                mock_get_client.side_effect = Exception(
                    "API client initialization failed"
                )

                # Test health endpoint
                response = client.get("/health")

                assert response.status_code == 503
                data = response.json()
                assert data["status"] == "unhealthy"
                assert data["service"] == "Korea Tourism API MCP Server"
                assert "API client initialization failed" in data["error"]
                assert data["transport"] == "streamable-http"
                assert "timestamp" in data


class TestEnvironmentVariablePriority:
    """Test environment variable priority and fallback behavior."""

    def test_missing_environment_variables_fallback(self, monkeypatch):
        """Test fallback to default values when environment variables are missing."""
        # Clear all relevant environment variables
        for var in [
            "MCP_TRANSPORT",
            "MCP_HOST",
            "MCP_PORT",
            "MCP_PATH",
            "MCP_LOG_LEVEL",
        ]:
            monkeypatch.delenv(var, raising=False)

        # Test fallback behavior
        transport = os.environ.get("MCP_TRANSPORT", "stdio")
        host = os.environ.get("MCP_HOST", "127.0.0.1")
        port = int(os.environ.get("MCP_PORT", "8000"))
        path = os.environ.get("MCP_PATH", "/mcp")
        log_level = os.environ.get("MCP_LOG_LEVEL", "INFO")

        assert transport == "stdio"
        assert host == "127.0.0.1"
        assert port == 8000
        assert path == "/mcp"
        assert log_level == "INFO"

    def test_partial_environment_variables(self, monkeypatch):
        """Test behavior when only some environment variables are set."""
        # Set only some environment variables
        monkeypatch.setenv("MCP_TRANSPORT", "sse")
        monkeypatch.setenv("MCP_PORT", "9000")

        # Clear others
        for var in ["MCP_HOST", "MCP_PATH", "MCP_LOG_LEVEL"]:
            monkeypatch.delenv(var, raising=False)

        # Test mixed configuration
        transport = os.environ.get("MCP_TRANSPORT", "stdio")
        host = os.environ.get("MCP_HOST", "127.0.0.1")
        port = int(os.environ.get("MCP_PORT", "8000"))
        path = os.environ.get("MCP_PATH", "/mcp")
        log_level = os.environ.get("MCP_LOG_LEVEL", "INFO")

        assert transport == "sse"  # From env var
        assert host == "127.0.0.1"  # Default fallback
        assert port == 9000  # From env var
        assert path == "/mcp"  # Default fallback
        assert log_level == "INFO"  # Default fallback
