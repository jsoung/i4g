import threading
import time
from unittest.mock import patch

import pytest
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from i4g.api.app import REQUEST_LOG, app, rate_limit_middleware

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_request_log():
    """A fixture to automatically clear the request log before each test."""
    REQUEST_LOG.clear()


async def mock_call_next(request):
    """A dummy function to simulate the 'call_next' in the middleware."""
    return JSONResponse(content={"message": "OK"})


@pytest.mark.anyio
async def test_rate_limiting_direct_call():
    """Unit test the middleware logic directly, bypassing the TestClient."""
    MAX_REQUESTS = 10
    TEST_IP = "127.0.0.1"

    scope = {
        "type": "http",
        "client": ("testclient", 123),
        "headers": [(b"x-forwarded-for", TEST_IP.encode())],
    }
    request = Request(scope)

    with patch("time.time") as mock_time:
        current_time = 1000000.0
        mock_time.return_value = current_time

        # Call middleware 10 times, they should pass
        for i in range(MAX_REQUESTS):
            await rate_limit_middleware(request, mock_call_next)

        # The 11th call should raise an exception
        with pytest.raises(HTTPException) as excinfo:
            await rate_limit_middleware(request, mock_call_next)

        assert excinfo.value.status_code == 429

        # Move time forward
        mock_time.return_value = current_time + 61

        # The 12th call should now pass
        await rate_limit_middleware(request, mock_call_next)


def test_report_generation_lock():
    """Test the report generation lock behavior."""
    from i4g.api.app import report_lock

    # Ensure the lock is released before starting the test
    while report_lock.locked():
        try:
            report_lock.release()
        except RuntimeError:
            break

    # Save original sleep function to avoid recursion
    original_sleep = time.sleep

    # Mock time.sleep with a shorter delay to make the test fast
    with patch("i4g.api.app.time.sleep", side_effect=lambda x: original_sleep(0.1)):
        # First request should succeed
        response1 = client.post("/reports/generate")
        assert response1.status_code == 200
        assert response1.json()["status"] == "started"

        # Immediately try a second request - should be locked
        response_locked = client.post("/reports/generate")
        assert response_locked.status_code == 423
        assert response_locked.json()["detail"] == "Report generation already in progress"

    # Wait a moment for the background thread to complete and release the lock
    time.sleep(0.3)

    # Now a new request should succeed
    with patch("i4g.api.app.time.sleep", side_effect=lambda x: original_sleep(0.1)):
        response2 = client.post("/reports/generate")
        assert response2.status_code == 200
        assert response2.json()["status"] == "started"

    # Wait for final cleanup
    time.sleep(0.3)
