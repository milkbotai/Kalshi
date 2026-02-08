# Integration Tests

Integration tests validate the complete API integrations with real external services.

## Running Integration Tests

### Run all integration tests:
```bash
pytest tests/integration/ -v -m integration
```

### Run only unit tests (skip integration):
```bash
pytest tests/unit/ -v
```

### Run all tests including integration:
```bash
pytest tests/ -v
```

### Skip slow tests:
```bash
pytest tests/ -v -m "not slow"
```

## Configuration

### NWS Integration Tests
NWS integration tests make real API calls to weather.gov. No credentials required.

These tests are marked with `@pytest.mark.integration` and `@pytest.mark.slow`.

### Kalshi Integration Tests
Kalshi integration tests require demo API credentials:

```bash
export KALSHI_API_KEY_ID="your_api_key_id"
export KALSHI_PRIVATE_KEY_PATH="/path/to/your/private_key.pem"
```

Tests will be skipped if credentials are not configured.

## Test Categories

- `test_nws_integration.py` - Real NWS API calls, response parsing, rate limiting
- `test_kalshi_integration.py` - Real Kalshi API calls, authentication, market data
- `test_end_to_end.py` - Complete workflows involving multiple APIs

## CI/CD Considerations

Integration tests can be slow and may fail due to external service issues.

Recommended CI strategy:
- Run unit tests on every commit
- Run integration tests nightly or on release branches
- Use pytest markers to control which tests run:
  ```bash
  pytest -m "not integration"  # Skip integration tests
  pytest -m "integration and not slow"  # Run fast integration tests only
  ```

## Rate Limiting

Integration tests respect API rate limits:
- NWS: 1 request/second
- Kalshi: 10 requests/second

Tests may take several seconds to complete due to rate limiting.
