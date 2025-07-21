"""
Integration tests for the MCP Tourism server.
Tests server initialization, tool registration, and basic functionality.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastmcp import Client
from mcp_tourism.server import mcp
from mcp_tourism.api_client import KoreaTourismApiClient


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up environment variables for testing."""
    monkeypatch.setenv("KOREA_TOURISM_API_KEY", "test-api-key-12345")
    monkeypatch.setenv("MCP_TOURISM_DEFAULT_LANGUAGE", "en")
    monkeypatch.setenv("MCP_TOURISM_CACHE_TTL", "3600")
    monkeypatch.setenv("MCP_TOURISM_RATE_LIMIT_CALLS", "10")
    monkeypatch.setenv("MCP_TOURISM_RATE_LIMIT_PERIOD", "1")
    monkeypatch.setenv("MCP_TOURISM_CONCURRENCY_LIMIT", "5")


@pytest.fixture
def mock_api_client():
    """Create a mock API client."""
    mock_client = MagicMock(spec=KoreaTourismApiClient)
    mock_client._ensure_full_initialization = MagicMock()

    # Mock async methods
    mock_client.search_by_keyword = AsyncMock()
    mock_client.get_area_based_list = AsyncMock()
    mock_client.get_location_based_list = AsyncMock()
    mock_client.search_festival = AsyncMock()
    mock_client.search_stay = AsyncMock()
    mock_client.get_detail_common = AsyncMock()
    mock_client.get_detail_intro = AsyncMock()
    mock_client.get_detail_info = AsyncMock()
    mock_client.get_detail_images = AsyncMock()
    mock_client.get_area_code_list = AsyncMock()

    return mock_client


@pytest.mark.asyncio
async def test_server_initialization_and_tools_list(mock_env_vars):
    """
    Test that the FastMCP server initializes correctly and all tools are registered.
    """
    # Create a client connected to our server
    client = Client(mcp)

    async with client:
        # Test that we can list tools without errors
        tools = await client.list_tools()

        # Expected tool names
        expected_tools = {
            "search_tourism_by_keyword",
            "get_tourism_by_area",
            "find_nearby_attractions",
            "search_festivals_by_date",
            "find_accommodations",
            "get_detailed_information",
            "get_tourism_images",
            "get_area_codes",
        }

        # Get actual tool names
        actual_tools = {tool.name for tool in tools}

        # Assert all expected tools are present
        assert expected_tools == actual_tools, (
            f"Expected tools: {expected_tools}, but got: {actual_tools}"
        )

        # Verify each tool has proper metadata
        for tool in tools:
            assert tool.name in expected_tools
            assert tool.description is not None and len(tool.description) > 0
            assert tool.inputSchema is not None


@pytest.mark.asyncio
@patch("mcp_tourism.server.get_api_client")
async def test_search_tourism_tool_execution(
    mock_get_api_client, mock_api_client, mock_env_vars
):
    """
    Test that we can actually call a tool through the MCP interface.
    """
    # Setup mock API client
    mock_get_api_client.return_value = mock_api_client
    mock_api_client.search_by_keyword.return_value = {
        "total_count": 1,
        "items": [{"title": "Test Attraction", "content_id": "123"}],
        "page_no": 1,
        "num_of_rows": 1,
    }

    # Create a client connected to our server
    client = Client(mcp)

    async with client:
        # Call the search tool
        result = await client.call_tool(
            "search_tourism_by_keyword", {"keyword": "Seoul Tower"}
        )

        # Verify we got a result
        assert len(result) > 0

        # The result should be TextContent with JSON data (dict is auto-converted)
        assert result[0].type == "text"

        # Verify the mock was called correctly
        mock_api_client.search_by_keyword.assert_called_once_with(
            keyword="Seoul Tower",
            content_type_id=None,
            area_code=None,
            language=None,
            page=1,
            rows=20,
        )


@pytest.mark.asyncio
@patch("mcp_tourism.server.get_api_client")
async def test_tool_with_validation_error(
    mock_get_api_client, mock_api_client, mock_env_vars
):
    """
    Test that validation errors are properly handled and returned through MCP.
    """
    # Setup mock API client
    mock_get_api_client.return_value = mock_api_client

    # Create a client connected to our server
    client = Client(mcp)

    async with client:
        # Call the search tool with invalid content_type
        with pytest.raises(Exception) as exc_info:
            await client.call_tool(
                "search_tourism_by_keyword",
                {"keyword": "Seoul Tower", "content_type": "InvalidType"},
            )

        # The error should mention the invalid type
        assert "InvalidType" in str(exc_info.value)
        assert "Valid types are:" in str(exc_info.value)

        # The API client should not have been called
        mock_api_client.search_by_keyword.assert_not_called()


@pytest.mark.asyncio
async def test_server_tools_have_correct_parameters(mock_env_vars):
    """
    Test that all tools have the correct parameter schemas.
    """
    client = Client(mcp)

    async with client:
        tools = await client.list_tools()

        # Find the search_tourism_by_keyword tool
        search_tool = None
        for tool in tools:
            if tool.name == "search_tourism_by_keyword":
                search_tool = tool
                break

        assert search_tool is not None, "search_tourism_by_keyword tool not found"

        # Check that the tool has the expected parameters
        schema = search_tool.inputSchema
        assert "properties" in schema

        properties = schema["properties"]

        # Required parameter
        assert "keyword" in properties
        assert properties["keyword"]["type"] == "string"

        # Optional parameters
        optional_params = ["content_type", "area_code", "language", "page", "rows"]
        for param in optional_params:
            assert param in properties

        # Check that keyword is required
        assert "required" in schema
        assert "keyword" in schema["required"]


@pytest.mark.asyncio
@patch("mcp_tourism.server.get_api_client")
async def test_multiple_tool_calls(mock_get_api_client, mock_api_client, mock_env_vars):
    """
    Test that we can make multiple tool calls successfully.
    """
    # Setup mock API client
    mock_get_api_client.return_value = mock_api_client

    # Setup different mock responses
    mock_api_client.search_by_keyword.return_value = {"total_count": 5, "items": []}
    mock_api_client.get_area_code_list.return_value = {"total_count": 3, "items": []}

    client = Client(mcp)

    async with client:
        # Make first tool call
        result1 = await client.call_tool(
            "search_tourism_by_keyword", {"keyword": "Busan"}
        )

        # Make second tool call
        result2 = await client.call_tool("get_area_codes", {"parent_area_code": "1"})

        # Both calls should succeed
        assert len(result1) > 0
        assert len(result2) > 0

        # Verify both mocks were called
        mock_api_client.search_by_keyword.assert_called_once()
        mock_api_client.get_area_code_list.assert_called_once()


@pytest.mark.asyncio
async def test_server_ping(mock_env_vars):
    """
    Test that we can ping the server successfully.
    """
    client = Client(mcp)

    async with client:
        # Ping server - should not raise an exception
        await client.ping()

        # Also test that we can list tools to ensure server is responsive
        tools = await client.list_tools()
        assert len(tools) > 0
