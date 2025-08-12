import httpx
import logging
import asyncio
import urllib.parse
import json
import codecs
from typing import Dict, Optional, Any, Literal, ClassVar
from cachetools import TTLCache
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from ratelimit import limits, sleep_and_retry


# Map of content type IDs to their human-readable names
CONTENTTYPE_ID_MAP = {
    "76": "Tourist Attraction",
    "78": "Cultural Facility",
    "85": "Festival Event",
    "75": "Leisure Activity",
    "80": "Accommodation",
    "79": "Shopping",
    "82": "Restaurant",
    "77": "Transportation",
}

# Map of supported languages to their service endpoints
LANGUAGE_SERVICE_MAP = {
    "en": "EngService2",  # English
    "jp": "JpnService2",  # Japanese
    "zh-cn": "ChsService2",  # Simplified Chinese
    "zh-tw": "ChtService2",  # Traditional Chinese
    "de": "GerService2",  # German
    "fr": "FreService2",  # French
    "es": "SpnService2",  # Spanish
    "ru": "RusService2",  # Russian
}


def decode_unicode_escapes(obj: Any) -> Any:
    """
    Recursively decode unicode escape sequences in strings within data structures.
    This helps resolve Korean character encoding issues like \\uc11c\\uc6b8 -> 서울.
    Only processes strings that actually contain unicode escape sequences.
    """
    if isinstance(obj, str):
        # Only attempt decoding if the string contains unicode escape sequences
        if "\\u" in obj:
            try:
                # Try to decode unicode escape sequences (e.g., \\uc11c\\uc6b8 -> 서울)
                return codecs.decode(obj, "unicode_escape")
            except (UnicodeDecodeError, ValueError):
                # If decoding fails, return original string
                return obj
        else:
            # If no escape sequences, return as-is
            return obj
    elif isinstance(obj, dict):
        return {key: decode_unicode_escapes(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [decode_unicode_escapes(item) for item in obj]
    else:
        return obj


class TourismApiError(Exception):
    """Base exception for Tourism API errors"""

    def __init__(
        self,
        message: str,
        response: Optional[httpx.Response] = None,
        request: Optional[httpx.Request] = None,
    ):
        super().__init__(message)
        self.message = message
        self.response = response
        self.request = request

    def __str__(self) -> str:
        base_str = super().__str__()
        if self.response:
            base_str += f" (Status Code: {self.response.status_code})"
        if self.request:
            base_str += f" (Request URL: {self.request.url})"
        return base_str


class TourismApiConnectionError(TourismApiError):
    """Connection error with Tourism API"""

    # Usually no response, so focus on request
    def __init__(self, message: str, request: Optional[httpx.Request] = None):
        super().__init__(message, response=None, request=request)


class TourismApiClientError(TourismApiError):
    """Client-side error with Tourism API requests (4xx)"""

    pass


class TourismApiServerError(TourismApiError):
    """Server-side error with Tourism API operations (5xx)"""

    pass


class KoreaTourismApiClient:
    """
    Client for the Korea Tourism Organization API with caching and rate limiting.

    Features:
    - Multi-language support
    - Response caching with TTL
    - Rate limiting to respect API quotas
    - Automatic retries for transient errors
    - Connection pooling
    """

    # Base URL for all services
    BASE_URL = "http://apis.data.go.kr/B551011"

    # --- Constants for API Parameters ---
    DEFAULT_NUM_OF_ROWS = 100
    DEFAULT_PAGE_NO = 1
    MOBILE_OS = "ETC"
    MOBILE_APP = "MobileApp"
    RESPONSE_FORMAT = "json"
    ARRANGE_MODIFIED_WITH_IMAGE = "Q"  # Sort by modified date with image
    # --- End Constants ---

    # Common endpoints (will be prefixed with service name)
    AREA_BASED_LIST_ENDPOINT = "/areaBasedList2"
    LOCATION_BASED_LIST_ENDPOINT = "/locationBasedList2"
    SEARCH_KEYWORD_ENDPOINT = "/searchKeyword2"
    SEARCH_FESTIVAL_ENDPOINT = "/searchFestival2"
    SEARCH_STAY_ENDPOINT = "/searchStay2"
    DETAIL_COMMON_ENDPOINT = "/detailCommon2"
    DETAIL_INTRO_ENDPOINT = "/detailIntro2"
    DETAIL_INFO_ENDPOINT = "/detailInfo2"
    DETAIL_IMAGE_ENDPOINT = "/detailImage2"
    AREA_BASED_SYNC_LIST_ENDPOINT = "/areaBasedSyncList2"
    AREA_CODE_LIST_ENDPOINT = "/areaCode2"
    CATEGORY_CODE_LIST_ENDPOINT = "/categoryCode2"

    # Class-level connection pool and semaphore for concurrency control
    _shared_client: ClassVar[Optional[httpx.AsyncClient]] = None
    _client_lock: ClassVar[asyncio.Lock] = asyncio.Lock()
    # Make concurrency limit configurable
    # _request_semaphore: ClassVar[asyncio.Semaphore] = asyncio.Semaphore(10)

    def __init__(
        self,
        api_key: str,
        language: str = "en",
        cache_ttl: int = 86400,
        rate_limit_calls: int = 5,
        rate_limit_period: int = 1,
        concurrency_limit: int = 10,
    ):
        """
        Initialize with API key and optional configurations.

        Args:
            api_key: The API key for the Korea Tourism Organization.
            language: Default language code for content (en, ko, jp, etc.).
            cache_ttl: Time-to-live for cached responses in seconds.
            rate_limit_calls: Maximum number of API calls allowed.
            rate_limit_period: Time period (in seconds) for the rate limit.
            concurrency_limit: Maximum number of concurrent API requests.
        """
        self.api_key = api_key
        if (
            not self.api_key or self.api_key == "missing_api_key"
        ):  # Check for placeholder too
            # Log warning here instead of raising immediately, allows lazy init check
            logging.warning("Korean Tourism API key is missing or invalid.")
            # We don't raise here because get_api_client in server.py handles this

        self._logger_name = "tourism_api_client"

        # Store configuration parameters
        self.default_language = language.lower()
        self.language: Optional[str] = None  # Initialize language attribute
        self._cache_ttl = cache_ttl
        self._rate_limit_calls = rate_limit_calls
        self._rate_limit_period = rate_limit_period
        self._concurrency_limit = concurrency_limit

        # Lazy initialization flags/placeholders
        self.service_name: Optional[str] = None
        self.full_base_url: Optional[str] = None
        self._is_fully_initialized = False
        self._cache: Optional[TTLCache] = None
        self._request_semaphore: Optional[asyncio.Semaphore] = None
        self.logger: Optional[logging.Logger] = None  # Add logger type hint

    def _ensure_full_initialization(self):
        """Ensure all initialization tasks are completed before first API request"""
        if self._is_fully_initialized:
            return

        # Get logger first
        self.logger = logging.getLogger(self._logger_name)
        if (
            not self.logger.hasHandlers()
        ):  # Basic check to prevent duplicate handlers if called multiple times
            logging.basicConfig(level=logging.INFO)  # Basic config if not already set

        # Validate API key presence here before proceeding
        if not self.api_key or self.api_key == "missing_api_key":
            self.logger.error("Cannot proceed without a valid KOREA_TOURISM_API_KEY.")
            # Raising here prevents further operations if key is truly missing
            raise ValueError("Korean Tourism API key must be provided and valid.")

        # Initialize language service using the stored default
        self.language = self.default_language
        if self.language not in LANGUAGE_SERVICE_MAP:
            self.logger.warning(
                f"Unsupported language: {self.language}. Falling back to English."
            )
            self.language = "en"

        self.service_name = LANGUAGE_SERVICE_MAP[self.language]
        self.full_base_url = f"{self.BASE_URL}/{self.service_name}"

        # Initialize cache with configured TTL
        self._cache = TTLCache(maxsize=1000, ttl=self._cache_ttl)

        # Initialize semaphore with configured concurrency limit
        self._request_semaphore = asyncio.Semaphore(self._concurrency_limit)

        self._is_fully_initialized = True

    @property
    def cache(self) -> TTLCache:
        """Lazy cache initialization"""
        self._ensure_full_initialization()
        return self._cache  # type: ignore  # We know it's initialized after _ensure_full_initialization

    @classmethod
    async def get_shared_client(cls) -> httpx.AsyncClient:
        """Get or create the shared HTTP client with connection pooling"""
        async with cls._client_lock:
            if cls._shared_client is None:
                cls._shared_client = httpx.AsyncClient(
                    limits=httpx.Limits(
                        max_connections=100, max_keepalive_connections=20
                    ),
                    timeout=httpx.Timeout(30.0),
                )
            return cls._shared_client

    @classmethod
    async def close_all_connections(cls):
        """Close the shared client connection - call this when your application is shutting down"""
        async with cls._client_lock:
            if cls._shared_client is not None:
                await cls._shared_client.aclose()
                cls._shared_client = None

    def _process_response_error(self, response: httpx.Response):
        """Process HTTP errors and raise appropriate exceptions"""
        # Check status code first for efficiency
        if response.status_code >= 400:
            status_code = response.status_code
            request = response.request  # Get the request object

            # Try to extract error message
            error_msg = f"Tourism API error: HTTP {status_code}"
            try:
                error_data = response.json()
                if isinstance(error_data, dict) and "error" in error_data:
                    error_msg = f"Tourism API error: {error_data['error']}"
            except Exception:
                pass

            # Map status code to exception type
            if status_code >= 400 and status_code < 500:
                # Pass response and request to the exception
                raise TourismApiClientError(
                    f"Client error: {error_msg}", response=response, request=request
                )
            else:
                # Pass response and request to the exception
                raise TourismApiServerError(
                    f"Server error: {error_msg}", response=response, request=request
                )

    def _get_cache_key(
        self, endpoint: str, params: Dict[str, Any], language: str
    ) -> str:
        """Generate a unique cache key for an API request, including language."""
        # Sort params to ensure consistent keys, exclude common/dynamic ones
        sorted_params = sorted(
            [
                (k, v)
                for k, v in params.items()
                if k not in ("MobileOS", "MobileApp", "serviceKey", "_type")
            ]
        )
        # Include language in cache key
        param_str = f"lang={language}&" + "&".join(
            [f"{k}={v}" for k, v in sorted_params]
        )
        return f"{endpoint}?{param_str}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(
            (httpx.ConnectTimeout, httpx.ConnectError, TourismApiServerError)
        ),
        reraise=True,
    )
    async def _make_request(
        self,
        endpoint: str,
        params: Dict[str, Any],
        use_cache: bool = True,
        language_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Make a request to the API with caching, rate limiting, and language override."""
        # Ensure all initialization is completed
        self._ensure_full_initialization()
        # After initialization, these are guaranteed to be not None
        assert self._request_semaphore is not None

        # Determine the language and base URL for this specific request
        request_language = self.language or "en"  # Fallback to English if None
        if language_override:
            lang_lower = language_override.lower()
            if lang_lower in LANGUAGE_SERVICE_MAP:
                request_language = lang_lower

        request_service_name = LANGUAGE_SERVICE_MAP[request_language]
        request_full_base_url = f"{self.BASE_URL}/{request_service_name}"

        # Check cache first if caching is enabled, using the request-specific language
        if use_cache:
            cache_key = self._get_cache_key(endpoint, params, request_language)
            cached_response = self.cache.get(cache_key)
            if cached_response:
                return cached_response

        # Apply rate limiting dynamically here using instance attributes
        @sleep_and_retry
        @limits(calls=self._rate_limit_calls, period=self._rate_limit_period)
        async def rate_limited_request() -> Dict[str, Any]:
            # Use concurrency semaphore to limit simultaneous requests
            semaphore = self._request_semaphore
            assert semaphore is not None, "Semaphore should be initialized"
            async with semaphore:
                # Add common parameters using constants
                full_params = {
                    "MobileOS": self.MOBILE_OS,
                    "MobileApp": self.MOBILE_APP,
                    # Defaults like numOfRows/pageNo are better set by calling methods or API defaults
                    "_type": self.RESPONSE_FORMAT,
                    **params,
                }

                # API key handling remains the same for now
                serviceKey = (
                    self.api_key
                )  # Already validated in _ensure_full_initialization

                # Build the full URL with the determined service for this request
                url = f"{request_full_base_url}{endpoint}"

                client = await self.get_shared_client()

                # First, encode the parameters
                encoded_params = urllib.parse.urlencode(full_params)

                # Then append the already-encoded service key
                full_url = f"{url}?serviceKey={serviceKey}&{encoded_params}"
                response = await client.get(full_url)

                self._process_response_error(response)

                # Parse the response with better error handling
                try:
                    # Check if the response has content
                    if not response.content or len(response.content.strip()) == 0:
                        raise TourismApiError(
                            "Empty response received from tourism API"
                        )

                    result = response.json()
                except json.JSONDecodeError as e:
                    raise TourismApiError(f"Invalid JSON response: {str(e)}")

                # Extract the items from the nested response structure
                try:
                    response_header = result["response"]["header"]
                    response_body = result["response"]["body"]

                    result_code = response_header.get("resultCode")
                    if result_code != "0000":
                        raise TourismApiError(
                            f"API error: {response_header.get('resultMsg', 'Unknown error')}"
                        )

                    total_count = response_body.get("totalCount", 0)
                    items = []

                    if total_count > 0:
                        items_container = response_body.get("items", {})
                        if "item" in items_container:
                            items = items_container["item"]
                            if not isinstance(items, list):
                                items = [
                                    items
                                ]  # Ensure items is a list even if there's only one result

                    # Structure the results
                    result_data = {
                        "total_count": total_count,
                        "num_of_rows": response_body.get("numOfRows", 0),
                        "page_no": response_body.get("pageNo", 1),
                        "items": items,
                    }

                    # Apply unicode decoding to handle Korean character encoding issues
                    result_data = decode_unicode_escapes(result_data)

                    # Cache the response if caching is enabled, using the request-specific language
                    if use_cache:
                        cache_key = self._get_cache_key(
                            endpoint, params, request_language
                        )
                        self.cache[cache_key] = result_data

                    return result_data

                except (KeyError, TypeError) as e:
                    raise TourismApiError(f"Failed to parse API response: {e}")

        # Call the inner function that has the decorators applied
        result = rate_limited_request()
        return await result  # type: ignore[misc]

    async def search_by_keyword(
        self,
        keyword: str,
        content_type_id: Optional[str] = None,
        area_code: Optional[str] = None,
        sigungu_code: Optional[str] = None,
        cat1: Optional[str] = None,
        cat2: Optional[str] = None,
        cat3: Optional[str] = None,
        language: Optional[str] = None,
        page: int = 1,
        rows: int = 20,
    ) -> Dict[str, Any]:
        """
        Search tourism information by keyword.
        /searchKeyword1

        Args:
            keyword: Search keyword (required)
            content_type_id: Content type ID to filter results
            area_code: Area code to filter results
            sigungu_code: Sigungu code to filter results, areaCode is required
            cat1: Major category code
            cat2: Middle category code (requires cat1)
            cat3: Minor category code (requires cat1 and cat2)
            language: Override the client's default language
            page: Page number for pagination
            rows: Number of items per page

        Returns:
            Dictionary containing search results with structure:
            {
                "total_count": int,     # Total number of matching items
                "num_of_rows": int,     # Number of items per page
                "page_no": int,         # Current page number
                "items": [              # List of tourism items
                    {
                        "title": str,           # Name of the attraction/place
                        "addr1": str,           # Primary address
                        "addr2": str,           # Secondary address
                        "areacode": str,        # Area code
                        "sigungucode": str,     # Sigungu code
                        "cat1": str,            # Category 1 code
                        "cat2": str,            # Category 2 code
                        "cat3": str,            # Category 3 code
                        "contentid": str,       # Unique content ID
                        "contenttypeid": str,   # Content type ID
                        "createdtime": str,     # Creation timestamp
                        "modifiedtime": str,    # Last modified timestamp
                        "tel": str,             # Phone number
                        "firstimage": str,      # URL of main image
                        "firstimage2": str,     # URL of thumbnail image
                        "mapx": str,            # Longitude
                        "mapy": str,            # Latitude
                        "mlevel": str,          # Map level
                        "cpyrhtDivCd": str      # Copyright division code
                    },
                    # ... more items
                ]
            }
        """
        if not keyword:
            raise ValueError("Keyword must be provided for search_by_keyword")

        params: Dict[str, Any] = {
            "keyword": keyword,
            "arrange": self.ARRANGE_MODIFIED_WITH_IMAGE,
            "pageNo": str(page),
            "numOfRows": str(rows),
        }

        if content_type_id:
            params["contentTypeId"] = content_type_id

        if area_code:
            params["areaCode"] = area_code

            if sigungu_code:
                params["sigunguCode"] = sigungu_code

        if cat1:
            params["cat1"] = cat1

            if cat2:
                params["cat2"] = cat2

                if cat3:
                    params["cat3"] = cat3

        # Pass language override directly to _make_request
        return await self._make_request(
            self.SEARCH_KEYWORD_ENDPOINT, params, language_override=language
        )

    async def get_area_based_list(
        self,
        area_code: Optional[str] = None,
        content_type_id: Optional[str] = None,
        sigunguCode: Optional[str] = None,
        cat1: Optional[str] = None,
        cat2: Optional[str] = None,
        cat3: Optional[str] = None,
        language: Optional[str] = None,
        page: int = 1,
        rows: int = 20,
    ) -> Dict[str, Any]:
        """
        Get a list of tourism information by area.

        Args:
            area_code: Area code to filter results
            content_type_id: Content type ID to filter results
            cat1: Major category code
            cat2: Middle category code (requires cat1)
            cat3: Minor category code (requires cat1 and cat2)
            language: Override the client's default language
            page: Page number for pagination
            rows: Number of items per page
            sigunguCode: Sigungu code to filter results, areaCode is required
        Returns:
            Dictionary containing area-based tourism information with structure:
            {
                "total_count": int,     # Total number of matching items
                "num_of_rows": int,     # Number of items per page
                "page_no": int,         # Current page number
                "items": [              # List of tourism items
                    {
                        "title": str,           # Name of the attraction/place
                        "addr1": str,           # Primary address
                        "addr2": str,           # Secondary address
                        "areacode": str,        # Area code
                        "sigungucode": str,     # Sigungu code
                        "cat1": str,            # Category 1 code
                        "cat2": str,            # Category 2 code
                        "cat3": str,            # Category 3 code
                        "contentid": str,       # Unique content ID
                        "contenttypeid": str,   # Content type ID
                        "createdtime": str,     # Creation timestamp
                        "modifiedtime": str,    # Last modified timestamp
                        "tel": str,             # Phone number
                        "firstimage": str,      # URL of main image
                        "firstimage2": str,     # URL of thumbnail image
                        "mapx": str,            # Longitude
                        "mapy": str,            # Latitude
                        "zipcode": str,         # Postal code
                        "mlevel": str           # Map level
                    },
                    # ... more items
                ]
            }
        """
        params: Dict[str, Any] = {
            "arrange": self.ARRANGE_MODIFIED_WITH_IMAGE,
            "pageNo": str(page),
            "numOfRows": str(rows),
            # "_type": self.RESPONSE_FORMAT, # Added in _make_request
        }

        # Add optional filters
        if area_code:
            params["areaCode"] = area_code
            if sigunguCode:
                params["sigunguCode"] = sigunguCode

        if content_type_id:
            params["contentTypeId"] = content_type_id

        # Add category filters if provided
        if cat1:
            params["cat1"] = cat1

            if cat2:
                params["cat2"] = cat2

                if cat3:
                    params["cat3"] = cat3

        # Pass language override directly to _make_request
        return await self._make_request(
            self.AREA_BASED_LIST_ENDPOINT, params, language_override=language
        )

    async def get_location_based_list(
        self,
        mapx: float,
        mapy: float,
        radius: int,
        content_type_id: Optional[str] = None,
        language: Optional[str] = None,
        page: int = 1,
        rows: int = 20,
    ) -> Dict[str, Any]:
        """
        Get a list of tourism information by location.

        Args:
            mapx: Map X coordinate
            mapy: Map Y coordinate
            radius: Radius in meters
            content_type_id: Content type ID from the tourism API
            language: Override the client's default language
            page: Page number for pagination
            rows: Number of items per page

        Returns:
            Dictionary containing location-based tourism information with structure:
            {
                "total_count": int,     # Total number of matching items
                "num_of_rows": int,     # Number of items per page
                "page_no": int,         # Current page number
                "items": [              # List of tourism items
                    {
                        "title": str,           # Name of the attraction/place
                        "addr1": str,           # Primary address
                        "addr2": str,           # Secondary address
                        "areacode": str,        # Area code
                        "sigungucode": str,     # Sigungu code
                        "cat1": str,            # Category 1 code
                        "cat2": str,            # Category 2 code
                        "cat3": str,            # Category 3 code
                        "contentid": str,       # Unique content ID
                        "contenttypeid": str,   # Content type ID
                        "createdtime": str,     # Creation timestamp
                        "modifiedtime": str,    # Last modified timestamp
                        "tel": str,             # Phone number
                        "firstimage": str,      # URL of main image
                        "firstimage2": str,     # URL of thumbnail image
                        "mapx": str,            # Longitude
                        "mapy": str,            # Latitude
                        "mlevel": str,          # Map level
                        "dist": str             # Distance from the specified coordinates
                    },
                    # ... more items
                ]
            }
        """
        # Parameter validation
        if mapx is None or mapy is None or radius is None:
            raise ValueError(
                "mapx, mapy, and radius are required for location-based search"
            )
        try:
            # Ensure radius is a positive integer
            radius_int = int(radius)
            if radius_int <= 0:
                raise ValueError("radius must be a positive integer")
        except ValueError:
            raise ValueError("radius must be a valid integer")

        params: Dict[str, Any] = {
            "pageNo": str(page),
            "numOfRows": str(rows),
            "arrange": self.ARRANGE_MODIFIED_WITH_IMAGE,
            "mapX": str(mapx),
            "mapY": str(mapy),
            "radius": str(radius_int),
        }

        if content_type_id:
            params["contentTypeId"] = content_type_id

        # Pass language override directly to _make_request
        return await self._make_request(
            self.LOCATION_BASED_LIST_ENDPOINT, params, language_override=language
        )

    async def search_festival(
        self,
        event_start_date: str,
        event_end_date: Optional[str] = None,
        area_code: Optional[str] = None,
        sigungu_code: Optional[str] = None,
        language: Optional[str] = None,
        page: int = 1,
        rows: int = 20,
    ) -> Dict[str, Any]:
        """
        Search for festivals by date and location.

        Args:
            event_start_date: Start date of the event (YYYYMMDD)
            event_end_date: End date of the event (YYYYMMDD)
            area_code: Area code to filter results
            sigungu_code: Sigungu code to filter results, areaCode is required
            language: Override the client's default language
            page: Page number for pagination
            rows: Number of items per page

        Returns:
            Dictionary containing festival information with structure:
            {
                "total_count": int,     # Total number of matching items
                "num_of_rows": int,     # Number of items per page
                "page_no": int,         # Current page number
                "items": [              # List of festival items
                    {
                        "title": str,           # Name of the festival
                        "addr1": str,           # Primary address
                        "addr2": str,           # Secondary address
                        "areacode": str,        # Area code
                        "contentid": str,       # Unique content ID
                        "contenttypeid": str,   # Content type ID
                        "createdtime": str,     # Creation timestamp
                        "eventstartdate": str,  # Festival start date
                        "eventenddate": str,    # Festival end date
                        "firstimage": str,      # URL of main image
                        "firstimage2": str,     # URL of thumbnail image
                        "mapx": str,            # Longitude
                        "mapy": str,            # Latitude
                        "mlevel": str,          # Map level
                        "tel": str,             # Phone number
                        "cat1": str,            # Category 1 code
                        "cat2": str,            # Category 2 code
                        "cat3": str             # Category 3 code
                    },
                    # ... more items
                ]
            }
        """
        if not event_start_date:
            raise ValueError("event_start_date (YYYYMMDD) is required")
        # Basic format check (can be improved with regex)
        if not (
            isinstance(event_start_date, str)
            and len(event_start_date) == 8
            and event_start_date.isdigit()
        ):
            raise ValueError("event_start_date must be in YYYYMMDD format")
        if event_end_date and not (
            isinstance(event_end_date, str)
            and len(event_end_date) == 8
            and event_end_date.isdigit()
        ):
            raise ValueError("event_end_date must be in YYYYMMDD format")

        params: Dict[str, Any] = {
            "eventStartDate": event_start_date,
            "pageNo": str(page),
            "numOfRows": str(rows),
            "arrange": self.ARRANGE_MODIFIED_WITH_IMAGE,  # Default arrange added
        }

        if event_end_date:
            params["eventEndDate"] = event_end_date

        if area_code:
            params["areaCode"] = area_code

            if sigungu_code:
                params["sigunguCode"] = sigungu_code

        # Pass language override directly to _make_request
        return await self._make_request(
            self.SEARCH_FESTIVAL_ENDPOINT, params, language_override=language
        )

    async def search_stay(
        self,
        area_code: Optional[str] = None,
        sigungu_code: Optional[str] = None,
        rows: int = 20,
        page: int = 1,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Search for stays by area and sigungu.

        Args:
            area_code: Area code to filter results
            sigungu_code: Sigungu code to filter results, areaCode is required
            rows: Number of items per page
            page: Page number for pagination
            language: Override the client's default language

        Returns:
            Dictionary containing accommodation information with structure:
            {
                "total_count": int,     # Total number of matching items
                "num_of_rows": int,     # Number of items per page
                "page_no": int,         # Current page number
                "items": [              # List of accommodation items
                    {
                        "title": str,           # Name of the accommodation
                        "addr1": str,           # Primary address
                        "addr2": str,           # Secondary address
                        "areacode": str,        # Area code
                        "sigungucode": str,     # Sigungu code
                        "contentid": str,       # Unique content ID
                        "contenttypeid": str,   # Content type ID
                        "createdtime": str,     # Creation timestamp
                        "firstimage": str,      # URL of main image
                        "firstimage2": str,     # URL of thumbnail image
                        "mapx": str,            # Longitude
                        "mapy": str,            # Latitude
                        "mlevel": str,          # Map level
                        "tel": str,             # Phone number
                        "cat1": str,            # Category 1 code
                        "cat2": str,            # Category 2 code
                        "cat3": str,            # Category 3 code
                        "hanok": str,           # Korean traditional house flag
                        "benikia": str,         # Benikia hotel flag
                        "goodstay": str         # Goodstay accommodation flag
                    },
                    # ... more items
                ]
            }
        """
        params: Dict[str, Any] = {
            "pageNo": str(page),
            "numOfRows": str(rows),
            "arrange": self.ARRANGE_MODIFIED_WITH_IMAGE,  # Default arrange added
        }

        if area_code:
            params["areaCode"] = area_code

            if sigungu_code:
                params["sigunguCode"] = sigungu_code

        # Pass language override directly to _make_request
        return await self._make_request(
            self.SEARCH_STAY_ENDPOINT, params, language_override=language
        )

    async def get_detail_common(
        self,
        content_id: str,
        content_type_id: Optional[str] = None,
        language: Optional[str] = None,
        rows: int = 20,
        page: int = 1,
    ) -> Dict[str, Any]:
        """
        Get common information by type basic information, schematic image,
        representative image, classification information, regional information,
        address information, coordinate information, outline information, road guidance information,
        image information, linked tourism information list

        Args:
            content_id: Content ID from the tourism API
            content_type_id: Content type ID from the tourism API
            language: Override the client's default language
            rows: Number of items per page
            page: Page number for pagination

        Returns:
            Dictionary containing common details about a tourism item with structure:
            {
                "total_count": int,     # Total number of matching items (typically 1)
                "num_of_rows": int,     # Number of items per page
                "page_no": int,         # Current page number
                "items": [              # List containing a single item's details
                    {
                        "title": str,           # Name of the item
                        "contentid": str,       # Unique content ID
                        "contenttypeid": str,   # Content type ID
                        "addr1": str,           # Primary address
                        "addr2": str,           # Secondary address
                        "areacode": str,        # Area code
                        "sigungucode": str,     # Sigungu code
                        "cat1": str,            # Category 1 code
                        "cat2": str,            # Category 2 code
                        "cat3": str,            # Category 3 code
                        "mapx": str,            # Longitude
                        "mapy": str,            # Latitude
                        "mlevel": str,          # Map level
                        "overview": str,        # Detailed description
                        "tel": str,             # Phone number
                        "telname": str,         # Contact name
                        "homepage": str,        # Website URL
                        "firstimage": str,      # URL of main image
                        "firstimage2": str,     # URL of thumbnail image
                        "createdtime": str,     # Creation timestamp
                        "modifiedtime": str,    # Last modified timestamp
                        "zipcode": str          # Postal code
                    }
                ]
            }
        """
        if not content_id:
            raise ValueError("content_id is required")

        params: Dict[str, Any] = {
            "contentId": content_id,
            "pageNo": str(page),
            "numOfRows": str(rows),
        }

        if content_type_id:
            params["contentTypeId"] = content_type_id

        # Pass language override directly to _make_request
        return await self._make_request(
            self.DETAIL_COMMON_ENDPOINT, params, language_override=language
        )

    async def get_detail_images(
        self,
        content_id: str,
        language: Optional[str] = None,
        image_yn: Literal["Y", "N"] = "Y",
        sub_image_yn: Literal["Y", "N"] = "Y",
        rows: int = 20,
        page: int = 1,
    ) -> Dict[str, Any]:
        """
        Get images for a tourism item.

        Args:
            content_id: Content ID from the tourism API
            language: Override the client's default language
            image_yn: Y=Content image inquiry N="Restaurant" type food menu image
            sub_image_yn: Y=Inquiry of original,thumbnail image,public Nuri copyright type information N=Null
            rows: Number of items per page
            page: Page number for pagination

        Returns:
            Dictionary containing images for a tourism item with structure:
            {
                "total_count": int,     # Total number of matching items
                "num_of_rows": int,     # Number of items per page
                "page_no": int,         # Current page number
                "items": [              # List of image items
                    {
                        "contentid": str,       # Content ID this image belongs to
                        "imgname": str,         # Image name
                        "originimgurl": str,    # URL of original image
                        "smallimageurl": str,   # URL of small/thumbnail image
                        "serialnum": str,       # Serial number
                        "cpyrhtDivCd": str      # Copyright division code
                    },
                    # ... more items
                ]
            }
        """
        if not content_id:
            raise ValueError("content_id is required")

        params: Dict[str, Any] = {
            "contentId": content_id,
            "imageYN": image_yn,
            "subImageYN": sub_image_yn,
            "numOfRows": str(rows),
            "pageNo": str(page),
        }

        # Pass language override directly to _make_request
        return await self._make_request(
            self.DETAIL_IMAGE_ENDPOINT, params, language_override=language
        )

    async def get_detail_intro(
        self,
        content_id: str,
        content_type_id: str,
        language: Optional[str] = None,
        rows: int = 20,
        page: int = 1,
    ) -> Dict[str, Any]:
        """
        Function to check detailed introduction (off day, opening period, etc.)

        Args:
            content_id: Content ID from the tourism API
            content_type_id: Content type ID from the tourism API
            language: Override the client's default language
            rows: Number of items per page
            page: Page number for pagination

        Returns:
            Dictionary containing detailed introduction information with structure:
            {
                "total_count": int,     # Total number of matching items
                "num_of_rows": int,     # Number of items per page
                "page_no": int,         # Current page number
                "items": [              # List containing a single item's intro details
                    {
                        "contentid": str,         # Content ID
                        "contenttypeid": str,     # Content type ID
                        # The following fields vary based on content_type_id:

                        # Attraction specific fields may include:
                        "infocenter": str,        # Information center
                        "restdate": str,          # Rest/closing days
                        "usetime": str,           # Hours of operation
                        "parking": str,           # Parking information
                        "chkbabycarriage": str,   # Baby carriage accessibility
                        "chkpet": str,            # Pet allowance
                        "chkcreditcard": str,     # Credit card acceptance

                        # Festival specific fields may include:
                        "eventstartdate": str,    # Festival start date
                        "eventenddate": str,      # Festival end date
                        "eventplace": str,        # Festival venue
                        "usetimefestival": str,   # Festival hours
                        "sponsor1": str,          # Primary sponsor
                        "sponsor2": str,          # Secondary sponsor

                        # Restaurant specific fields may include:
                        "firstmenu": str,         # Main menu items
                        "treatmenu": str,         # Specialty dishes
                        "opentimefood": str,      # Opening hours
                        "restdatefood": str,      # Closing days
                        "reservationfood": str,   # Reservation information

                        # Accommodation specific fields may include:
                        "checkintime": str,       # Check-in time
                        "checkouttime": str,      # Check-out time
                        "roomcount": str,         # Number of rooms
                        "reservationurl": str,    # Reservation website
                        "benikia": str,           # Benikia certification
                        "goodstay": str           # Goodstay certification
                    }
                ]
            }

            Note: The actual fields returned depend on the content_type_id and will vary between different types of tourism items.
        """
        if not content_id:
            raise ValueError("content_id is required")
        if not content_type_id:
            raise ValueError("content_type_id is required")
        params: Dict[str, Any] = {
            "contentId": content_id,
            "contentTypeId": content_type_id,
            "numOfRows": str(rows),
            "pageNo": str(page),
        }

        # Pass language override directly to _make_request
        return await self._make_request(
            self.DETAIL_INTRO_ENDPOINT, params, language_override=language
        )

    async def get_detail_info(
        self,
        content_id: str,
        content_type_id: str,
        language: Optional[str] = None,
        rows: int = 20,
        page: int = 1,
    ) -> Dict[str, Any]:
        """
        Check the details of additional tourism information.

        Args:
            content_id: Content ID from the tourism API
            content_type_id: Content type ID from the tourism API
            language: Override the client's default language
            rows: Number of items per page
            page: Page number for pagination

        Returns:
            Dictionary containing additional detailed information with structure:
            {
                "total_count": int,     # Total number of matching items
                "num_of_rows": int,     # Number of items per page
                "page_no": int,         # Current page number
                "items": [              # List of additional info items
                    {
                        "contentid": str,       # Content ID this info belongs to
                        "contenttypeid": str,   # Content type ID
                        "infoname": str,        # Name of the information
                        "infotext": str,        # Detailed text information
                        "fldgubun": str,        # Field division code
                        "serialnum": str        # Serial number
                    },
                    # ... more items
                ]
            }

            Note: Each item in the 'items' list represents a specific piece of additional information about the tourism item.
        """
        if not content_id:
            raise ValueError("content_id is required")
        if not content_type_id:
            raise ValueError("content_type_id is required")

        params: Dict[str, Any] = {
            "contentId": content_id,
            "contentTypeId": content_type_id,
            "numOfRows": str(rows),
            "pageNo": str(page),
        }

        # Pass language override directly to _make_request
        return await self._make_request(
            self.DETAIL_INFO_ENDPOINT, params, language_override=language
        )

    async def get_area_based_sync_list(
        self,
        content_type_id: Optional[str] = None,
        area_code: Optional[str] = None,
        sigungu_code: Optional[str] = None,
        cat1: Optional[str] = None,
        cat2: Optional[str] = None,
        cat3: Optional[str] = None,
        language: Optional[str] = None,
        show_flag: Optional[Literal["0", "1"]] = None,
        rows: int = 20,
        page: int = 1,
    ) -> Dict[str, Any]:
        """
        Detailed function of inquiring about the tourism information synchronization list (provided whether the contents are displayed or not)

        Args:
            area_code: Area code from the tourism API
            content_type_id: Content type ID from the tourism API
            sigungu_code: Sigungu code from the tourism API
            cat1: Category 1 from the tourism API
            cat2: Category 2 from the tourism API
            cat3: Category 3 from the tourism API
            language: Override the client's default language
            show_flag: Show flag from the tourism API
            rows: Number of items per page
            page: Page number for pagination

        Returns:
            Dictionary containing synchronized tourism information with structure:
            {
                "total_count": int,     # Total number of matching items
                "num_of_rows": int,     # Number of items per page
                "page_no": int,         # Current page number
                "items": [              # List of tourism items with sync status
                    {
                        "title": str,           # Name of the attraction/place
                        "addr1": str,           # Primary address
                        "addr2": str,           # Secondary address
                        "areacode": str,        # Area code
                        "sigungucode": str,     # Sigungu code
                        "cat1": str,            # Category 1 code
                        "cat2": str,            # Category 2 code
                        "cat3": str,            # Category 3 code
                        "contentid": str,       # Unique content ID
                        "contenttypeid": str,   # Content type ID
                        "createdtime": str,     # Creation timestamp
                        "modifiedtime": str,    # Last modified timestamp
                        "tel": str,             # Phone number
                        "firstimage": str,      # URL of main image
                        "firstimage2": str,     # URL of thumbnail image
                        "mapx": str,            # Longitude
                        "mapy": str,            # Latitude
                        "mlevel": str,          # Map level
                        "showflag": str         # Display status flag
                    },
                    # ... more items
                ]
            }
        """
        params: Dict[str, Any] = {
            "numOfRows": str(rows),  # Use str()
            "pageNo": str(page),  # Use str()
            "arrange": self.ARRANGE_MODIFIED_WITH_IMAGE,
        }
        if show_flag:
            params["showFlag"] = show_flag

        if area_code:
            params["areaCode"] = area_code

            if sigungu_code:
                params["sigunguCode"] = sigungu_code

        if cat1:
            params["cat1"] = cat1

            if cat2:
                params["cat2"] = cat2

                if cat3:
                    params["cat3"] = cat3

        if content_type_id:
            params["contentTypeId"] = content_type_id

        # Pass language override directly to _make_request
        return await self._make_request(
            self.AREA_BASED_SYNC_LIST_ENDPOINT, params, language_override=language
        )

    async def get_area_code_list(
        self,
        area_code: Optional[str] = None,
        language: Optional[str] = None,
        rows: int = 20,
        page: int = 1,
    ) -> Dict[str, Any]:
        """
        Get the list of area codes.

        Args:
            area_code: Area code from the tourism API
            language: Override the client's default language
            rows: Number of items per page
            page: Page number for pagination

        Returns:
            Dictionary containing area code information with structure:
            {
                "total_count": int,     # Total number of matching items
                "num_of_rows": int,     # Number of items per page
                "page_no": int,         # Current page number
                "items": [              # List of area code items
                    {
                        "code": str,            # Area code value
                        "name": str,            # Area name
                        "rnum": str             # Row number
                    },
                    # ... more items
                ]
            }

            If area_code is provided, returns sigungu codes for that area.
            If area_code is not provided, returns top-level area codes.
        """
        params: Dict[str, Any] = {
            "numOfRows": str(rows),  # Use str()
            "pageNo": str(page),  # Use str()
        }
        if area_code:
            params["areaCode"] = area_code

        # Pass language override directly to _make_request
        return await self._make_request(
            self.AREA_CODE_LIST_ENDPOINT, params, language_override=language
        )

    async def get_category_code_list(
        self,
        content_type_id: Optional[str] = None,
        language: Optional[str] = None,
        cat1: Optional[str] = None,
        cat2: Optional[str] = None,
        cat3: Optional[str] = None,
        rows: int = 20,
        page: int = 1,
    ) -> Dict[str, Any]:
        """
        Get the list of category codes.

        Args:
            content_type_id: Content type ID from the tourism API
            language: Override the client's default language
            cat1: Category 1 from the tourism API
            cat2: Category 2 from the tourism API
            cat3: Category 3 from the tourism API
            rows: Number of items per page
            page: Page number for pagination

        Returns:
            Dictionary containing category code information with structure:
            {
                "total_count": int,     # Total number of matching items
                "num_of_rows": int,     # Number of items per page
                "page_no": int,         # Current page number
                "items": [              # List of category code items
                    {
                        "code": str,            # Category code value
                        "name": str,            # Category name
                        "rnum": str             # Row number
                    },
                    # ... more items
                ]
            }

            The categories returned depend on the parameters provided:
            - Without any parameters: Returns top-level categories (cat1)
            - With cat1: Returns subcategories (cat2) under that cat1
            - With cat1 and cat2: Returns subcategories (cat3) under that cat2
        """
        params: Dict[str, Any] = {
            "numOfRows": str(rows),  # Use str()
            "pageNo": str(page),  # Use str()
        }

        if content_type_id:
            params["contentTypeId"] = content_type_id

        if cat1:
            params["cat1"] = cat1

            if cat2:
                params["cat2"] = cat2

                if cat3:
                    params["cat3"] = cat3

        # Pass language override directly to _make_request
        return await self._make_request(
            self.CATEGORY_CODE_LIST_ENDPOINT, params, language_override=language
        )


if __name__ == "__main__":
    import os
    import asyncio

    api_key = os.environ.get("KOREA_TOURISM_API_KEY")
    if not api_key:
        raise ValueError("KOREA_TOURISM_API_KEY environment variable is not set")
    client = KoreaTourismApiClient(api_key=api_key)
    print(asyncio.run(client.search_by_keyword(keyword="Gyeongbokgung")))
