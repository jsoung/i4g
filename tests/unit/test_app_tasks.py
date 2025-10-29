import pytest
from fastapi.testclient import TestClient
from i4g.api.app import app

client = TestClient(app)


def test_get_task_status_unknown():
    """Test retrieving the status of an unknown task."""
    task_id = "unknown_task"
    response = client.get(f"/tasks/{task_id}")
    assert response.status_code == 200
    assert response.json() == {
        "task_id": task_id,
        "status": "unknown",
        "message": "Task not found",
    }


def test_update_task_status():
    """Test updating the status of a task."""
    task_id = "test_task"
    payload = {"status": "in_progress", "message": "Generating report..."}

    # Update the task status
    response = client.post(f"/tasks/{task_id}/update", json=payload)
    assert response.status_code == 200
    assert response.json() == {"task_id": task_id, "updated": True}

    # Verify the updated status
    response = client.get(f"/tasks/{task_id}")
    assert response.status_code == 200
    assert response.json() == {"task_id": task_id, **payload}