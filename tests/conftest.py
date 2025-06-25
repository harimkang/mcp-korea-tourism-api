import pytest_asyncio
from mcp_tourism.api_client import KoreaTourismApiClient


@pytest_asyncio.fixture
async def client():
    """Provides a KoreaTourismApiClient instance for testing."""
    # Use a dummy API key for testing
    api_client = KoreaTourismApiClient(api_key="TEST_API_KEY")
    yield api_client
    # Clean up the shared client after tests if needed
    await KoreaTourismApiClient.close_all_connections()
