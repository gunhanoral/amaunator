import asyncio
from unittest.mock import AsyncMock

import pytest

from amaunator.core.manager import MonitorManager
from amaunator.models import Target


@pytest.fixture
def mock_queue():
    return AsyncMock(spec=asyncio.Queue)


async def noop_monitor(queue, target, stop_event):
    """A real coroutine mock for the monitor function."""
    pass


@pytest.fixture
def monitor_manager(mock_queue):
    # Pass a real coroutine function instead of MagicMock(return_value=AsyncMock())
    # because asyncio.create_task requires an actual coroutine object, not a Mock.
    return MonitorManager(mock_queue, monitor_func=noop_monitor)


@pytest.mark.asyncio
async def test_start_monitoring(monitor_manager):
    target = Target(name="Test Target", interval=10, timeout=2)

    monitor_manager.start_monitoring(target)

    assert target.id in monitor_manager.targets
    assert target.id in monitor_manager.tasks
    assert target.id in monitor_manager.stop_events
    assert monitor_manager.get_active_count() == 1
    assert monitor_manager.get_target(target.id) == target


@pytest.mark.asyncio
async def test_stop_monitoring(monitor_manager):
    target = Target(name="Test Target", interval=10, timeout=2)
    monitor_manager.start_monitoring(target)

    monitor_manager.stop_monitoring(target.id)

    assert target.id not in monitor_manager.targets
    assert target.id not in monitor_manager.tasks
    assert target.id not in monitor_manager.stop_events
    assert monitor_manager.get_active_count() == 0


@pytest.mark.asyncio
async def test_duplicate_start_ignored(monitor_manager):
    target = Target(name="Test Target", interval=10, timeout=2)
    monitor_manager.start_monitoring(target)

    # Try to start again
    monitor_manager.start_monitoring(target)

    assert monitor_manager.get_active_count() == 1


@pytest.mark.asyncio
async def test_stop_unknown_target(monitor_manager):
    target = Target(name="Test Target", interval=10, timeout=2)
    # Should not raise error
    monitor_manager.stop_monitoring(target.id)
