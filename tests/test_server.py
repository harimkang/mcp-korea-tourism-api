import pytest
import os
from unittest.mock import patch, MagicMock
from mcp_tourism.server import search_tourism_by_keyword, get_api_client, _api_client as server_api_client # Import necessary items
from mcp_tourism.api_client import KoreaTourismApiClient

# Fixture to reset the global API client before each test that needs it
@pytest.fixture(autouse=True)
def reset_global_client():
    global server_api_client
    server_api_client = None

# Fixture to provide a mocked API client instance
@pytest.fixture
def mock_api_client():
    mock_client = MagicMock(spec=KoreaTourismApiClient)
    mock_client._ensure_full_initialization = MagicMock() # Mock this method too
    return mock_client

@pytest.mark.asyncio
# Patch get_api_client to return our mock client instead of initializing a real one
@patch('mcp_tourism.server.get_api_client')
async def test_search_tourism_invalid_content_type(mock_get_api_client, mock_api_client):
    """
    Test that search_tourism_by_keyword raises ValueError for invalid content_type.
    """
    # Configure the mock get_api_client to return our fixture mock_api_client
    mock_get_api_client.return_value = mock_api_client
    
    invalid_type = "InvalidContentType"
    keyword = "Test"

    with pytest.raises(ValueError) as excinfo:
        await search_tourism_by_keyword(keyword=keyword, content_type=invalid_type)

    # Check that the error message contains the invalid type and mentions valid types
    assert invalid_type in str(excinfo.value)
    assert "Valid types are:" in str(excinfo.value)
    # Ensure the underlying client method was NOT called
    mock_api_client.search_by_keyword.assert_not_called()

@pytest.mark.parametrize(
    "env_var, invalid_value",
    [
        ("MCP_TOURISM_CACHE_TTL", "not-an-int"),
        ("MCP_TOURISM_RATE_LIMIT_CALLS", "five"),
        ("MCP_TOURISM_RATE_LIMIT_PERIOD", "one_sec"),
        ("MCP_TOURISM_CONCURRENCY_LIMIT", "10.5"),
    ]
)
def test_get_api_client_invalid_env_var(monkeypatch, env_var, invalid_value):
    """
    Test that get_api_client raises ValueError if env vars for int configs are invalid.
    """
    # Set a valid API key to avoid raising error for that
    monkeypatch.setenv("KOREA_TOURISM_API_KEY", "valid-key-for-test")
    # Set the invalid environment variable
    monkeypatch.setenv(env_var, invalid_value)

    # The 'reset_global_client' fixture with autouse=True automatically runs before this test,
    # ensuring server_api_client is None.

    # Calling get_api_client should raise ValueError during int conversion
    with pytest.raises(ValueError) as excinfo:
        get_api_client()

    # Check if the error message indicates an invalid literal for int()
    assert f"invalid literal for int() with base 10: '{invalid_value}'" in str(excinfo.value) 
    # Or check specifically for the variable name if preferred, though the standard
    # ValueError message for int() conversion is usually sufficient. 