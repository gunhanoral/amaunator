from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from amaunator.core.manager import MonitorManager
from amaunator.main import app
from amaunator.models import Target
from amaunator.outputs import OutputProcessor


@pytest.fixture
def client():
    # Mock the manager and processor
    mock_manager = MagicMock(spec=MonitorManager)
    mock_manager.start_time = 1000.0
    mock_manager.get_active_count.return_value = 5

    # Setup fake storage for get/list
    fake_target = Target(name="Test API", interval=10, timeout=2)
    mock_manager.get_target.return_value = fake_target
    mock_manager.get_all_targets.return_value = [fake_target]

    mock_processor = MagicMock(spec=OutputProcessor)
    mock_processor.processed_count = 42

    # Inject dependencies
    app.state.monitor_manager = mock_manager
    app.state.output_processor = mock_processor

    return TestClient(app)


def test_create_target(client):
    payload = {"name": "New Target", "interval": 5, "timeout": 1}
    response = client.post("/targets", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "New Target"
    assert "id" in data

    # Verify manager was called
    app.state.monitor_manager.start_monitoring.assert_called_once()


def test_list_targets(client):
    response = client.get("/targets")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test API"


def test_get_stats(client):
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["active_targets"] == 5
    assert data["processed_messages"] == 42


def test_delete_target(client):
    # Setup mock to return True for existence check
    target_id = "12345678-1234-5678-1234-567812345678"
    app.state.monitor_manager.get_target.return_value = Target(name="X", interval=1, timeout=1)

    response = client.delete(f"/targets/{target_id}")
    assert response.status_code == 204

    app.state.monitor_manager.stop_monitoring.assert_called_once()


def test_delete_missing_target(client):
    app.state.monitor_manager.get_target.return_value = None

    response = client.delete("/targets/12345678-1234-5678-1234-567812345678")
    assert response.status_code == 404
