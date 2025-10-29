import threading
import time
from unittest.mock import patch
import pytest
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

from fastapi.testclient import TestClient

from i4g.api.app import app, REQUEST_LOG, rate_limit_middleware

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

    scope = {"type": "http", "client": ("testclient", 123), "headers": [(b"x-forwarded-for", TEST_IP.encode())]}
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
    try:
        from i4g.api.app import report_lock
        if report_lock.locked():
            report_lock.release()
    except (ImportError, RuntimeError):
        pass

    def trigger_report_and_assert():
        response = client.post("/reports/generate")
        assert response.status_code == 200
        assert response.json()["status"] == "started"

    thread = threading.Thread(target=trigger_report_and_assert)
    thread.start()

    time.sleep(0.1)

    response_locked = client.post("/reports/generate")
    assert response_locked.status_code == 423
    assert response_locked.json()["detail"] == "Report generation already in progress"

    thread.join()

    final_thread = threading.Thread(target=trigger_report_and_assert)
    final_thread.start()
    final_thread.join()
