import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient
from starlette.applications import Starlette

from mcp_tourism.server import health_check, parse_server_config


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

        # Test the actual function
        transport, http_config = parse_server_config([])

        assert transport == "stdio"
        assert http_config == {}

    def test_command_line_argument_parsing(self):
        """Test command line argument parsing for transport configuration."""
        # Test with command line arguments using the actual function
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

        transport, http_config = parse_server_config(test_args)

        assert transport == "streamable-http"
        assert http_config["host"] == "0.0.0.0"
        assert http_config["port"] == 3000
        assert http_config["log_level"] == "DEBUG"
        assert http_config["path"] == "/api/mcp"

    def test_environment_variable_configuration(self, monkeypatch):
        """Test environment variable configuration."""
        # Set environment variables
        monkeypatch.setenv("MCP_TRANSPORT", "sse")
        monkeypatch.setenv("MCP_HOST", "127.0.0.1")
        monkeypatch.setenv("MCP_PORT", "8080")
        monkeypatch.setenv("MCP_LOG_LEVEL", "INFO")
        monkeypatch.setenv("MCP_PATH", "/mcp")

        # Test the actual function
        transport, http_config = parse_server_config([])

        assert transport == "sse"
        assert http_config["host"] == "127.0.0.1"
        assert http_config["port"] == 8080
        assert http_config["log_level"] == "INFO"
        assert http_config["path"] == "/mcp"

    def test_command_line_overrides_environment(self, monkeypatch):
        """Test that command line arguments override environment variables."""
        # Set environment variables
        monkeypatch.setenv("MCP_TRANSPORT", "sse")
        monkeypatch.setenv("MCP_HOST", "127.0.0.1")
        monkeypatch.setenv("MCP_PORT", "8080")

        # Test the actual function with CLI overrides
        transport, http_config = parse_server_config(
            ["--transport", "streamable-http", "--port", "3000"]
        )

        assert transport == "streamable-http"  # CLI override
        assert http_config["host"] == "127.0.0.1"  # From env var
        assert http_config["port"] == 3000  # CLI override

    def test_http_config_generation_for_streamable_http(self, monkeypatch):
        """Test HTTP configuration generation for streamable-http transport."""
        # Set up test environment
        monkeypatch.setenv("MCP_HOST", "0.0.0.0")
        monkeypatch.setenv("MCP_PORT", "8000")
        monkeypatch.setenv("MCP_LOG_LEVEL", "INFO")
        monkeypatch.setenv("MCP_PATH", "/mcp")

        # Test the actual function
        transport, http_config = parse_server_config(["--transport", "streamable-http"])

        assert transport == "streamable-http"
        assert http_config["host"] == "0.0.0.0"
        assert http_config["port"] == 8000
        assert http_config["log_level"] == "INFO"
        assert http_config["path"] == "/mcp"

    def test_http_config_generation_for_sse(self, monkeypatch):
        """Test HTTP configuration generation for SSE transport."""
        # Clear environment variables to test defaults
        for var in ["MCP_HOST", "MCP_PORT", "MCP_LOG_LEVEL", "MCP_PATH"]:
            monkeypatch.delenv(var, raising=False)

        # Test the actual function
        transport, http_config = parse_server_config(["--transport", "sse"])

        assert transport == "sse"
        assert http_config["host"] == "127.0.0.1"  # Default
        assert http_config["port"] == 8000  # Default
        assert http_config["log_level"] == "INFO"  # Default
        assert http_config["path"] == "/mcp"  # Default

    def test_stdio_transport_no_http_config(self):
        """Test that stdio transport doesn't generate HTTP config."""
        # Test the actual function
        transport, http_config = parse_server_config(["--transport", "stdio"])

        assert transport == "stdio"
        assert http_config == {}

    def test_invalid_transport_choice(self):
        """Test that invalid transport choices raise SystemExit."""
        with pytest.raises(SystemExit):
            parse_server_config(["--transport", "invalid-transport"])

    def test_invalid_port_type(self):
        """Test that invalid port type raises SystemExit."""
        with pytest.raises(SystemExit):
            parse_server_config(["--port", "not-a-number"])

    def test_invalid_log_level(self):
        """Test that invalid log level choices raise SystemExit."""
        with pytest.raises(SystemExit):
            parse_server_config(["--log-level", "INVALID"])

    def test_environment_variable_port_conversion_error(self, monkeypatch):
        """Test error handling when environment port variable is invalid."""
        monkeypatch.setenv("MCP_PORT", "not-a-number")

        with pytest.raises(ValueError):
            parse_server_config(["--transport", "streamable-http"])

    def test_all_cli_arguments_provided(self):
        """Test configuration when all CLI arguments are provided."""
        args = [
            "--transport",
            "sse",
            "--host",
            "192.168.1.100",
            "--port",
            "9999",
            "--log-level",
            "WARNING",
            "--path",
            "/custom/mcp/path",
        ]

        transport, http_config = parse_server_config(args)

        assert transport == "sse"
        assert http_config["host"] == "192.168.1.100"
        assert http_config["port"] == 9999
        assert http_config["log_level"] == "WARNING"
        assert http_config["path"] == "/custom/mcp/path"


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
        """Test that parse_server_config accepts valid transport choices."""
        # Test valid choices
        for transport in ["stdio", "streamable-http", "sse"]:
            result_transport, _ = parse_server_config(["--transport", transport])
            assert result_transport == transport

    def test_invalid_transport_choice(self):
        """Test that parser rejects invalid transport choices."""
        # Test invalid choice
        with pytest.raises(SystemExit):
            parse_server_config(["--transport", "invalid-transport"])

    def test_port_type_validation(self):
        """Test that parser validates port as integer."""
        # Test valid port
        _, http_config = parse_server_config(
            ["--transport", "streamable-http", "--port", "8000"]
        )
        assert http_config["port"] == 8000

        # Test invalid port
        with pytest.raises(SystemExit):
            parse_server_config(["--port", "not-a-number"])

    def test_log_level_choices(self):
        """Test that parser accepts valid log level choices."""
        # Test valid choices
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            _, http_config = parse_server_config(
                ["--transport", "streamable-http", "--log-level", level]
            )
            assert http_config["log_level"] == level

    def test_negative_port_value(self):
        """Test that negative port values are handled gracefully."""
        # Parser should accept negative values but they may not be practical
        _, http_config = parse_server_config(
            ["--transport", "streamable-http", "--port", "-1"]
        )
        assert http_config["port"] == -1

    def test_zero_port_value(self):
        """Test that zero port value is handled gracefully."""
        _, http_config = parse_server_config(
            ["--transport", "streamable-http", "--port", "0"]
        )
        assert http_config["port"] == 0

    def test_large_port_value(self):
        """Test that large port values are handled gracefully."""
        _, http_config = parse_server_config(
            ["--transport", "streamable-http", "--port", "65535"]
        )
        assert http_config["port"] == 65535


class TestServerIntegration:
    """Test server integration with different transports."""

    def test_mcp_server_with_stdio_transport(self, monkeypatch):
        """Test that MCP server can be configured with stdio transport."""
        # Set up environment
        monkeypatch.setenv("KOREA_TOURISM_API_KEY", "test-key")
        monkeypatch.setenv("MCP_TRANSPORT", "stdio")

        # Test the actual function
        transport, http_config = parse_server_config([])

        assert transport == "stdio"
        assert http_config == {}

    def test_http_config_preparation(self, monkeypatch):
        """Test HTTP configuration preparation for HTTP transports."""
        # Set up environment for HTTP transport
        monkeypatch.setenv("MCP_HOST", "0.0.0.0")
        monkeypatch.setenv("MCP_PORT", "3000")
        monkeypatch.setenv("MCP_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("MCP_PATH", "/api/mcp")

        # Test the actual function
        transport, http_config = parse_server_config(["--transport", "streamable-http"])

        # Verify configuration
        assert transport == "streamable-http"
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

        # Test the actual function with HTTP transport to verify defaults
        transport, http_config = parse_server_config(["--transport", "streamable-http"])

        assert transport == "streamable-http"
        assert http_config["host"] == "127.0.0.1"  # Default
        assert http_config["port"] == 8000  # Default
        assert http_config["path"] == "/mcp"  # Default
        assert http_config["log_level"] == "INFO"  # Default

    def test_partial_environment_variables(self, monkeypatch):
        """Test behavior when only some environment variables are set."""
        # Set only some environment variables
        monkeypatch.setenv("MCP_TRANSPORT", "sse")
        monkeypatch.setenv("MCP_PORT", "9000")

        # Clear others
        for var in ["MCP_HOST", "MCP_PATH", "MCP_LOG_LEVEL"]:
            monkeypatch.delenv(var, raising=False)

        # Test the actual function
        transport, http_config = parse_server_config([])

        assert transport == "sse"  # From env var
        assert http_config["host"] == "127.0.0.1"  # Default fallback
        assert http_config["port"] == 9000  # From env var
        assert http_config["path"] == "/mcp"  # Default fallback
        assert http_config["log_level"] == "INFO"  # Default fallback

    def test_environment_variable_empty_values(self, monkeypatch):
        """Test behavior when environment variables are set to empty values."""
        # Set environment variables to empty strings
        monkeypatch.setenv("MCP_HOST", "")
        monkeypatch.setenv("MCP_PATH", "")
        monkeypatch.setenv("MCP_LOG_LEVEL", "")

        # Test the actual function
        transport, http_config = parse_server_config(["--transport", "streamable-http"])

        assert transport == "streamable-http"
        # Empty string should be used instead of defaults
        assert http_config["host"] == ""
        assert http_config["path"] == ""
        assert http_config["log_level"] == ""
        assert http_config["port"] == 8000  # This should still be default since not set

    def test_cli_arguments_override_empty_env_vars(self, monkeypatch):
        """Test that CLI arguments override empty environment variables."""
        # Set environment variables to empty strings
        monkeypatch.setenv("MCP_HOST", "")
        monkeypatch.setenv("MCP_PATH", "")

        # Test with CLI overrides
        transport, http_config = parse_server_config(
            [
                "--transport",
                "streamable-http",
                "--host",
                "192.168.1.1",
                "--path",
                "/custom/path",
            ]
        )

        assert transport == "streamable-http"
        assert http_config["host"] == "192.168.1.1"  # CLI override
        assert http_config["path"] == "/custom/path"  # CLI override
        assert http_config["port"] == 8000  # Default
        assert http_config["log_level"] == "INFO"  # Default
