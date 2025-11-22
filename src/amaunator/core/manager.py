import asyncio
import time
from collections.abc import Awaitable, Callable
from uuid import UUID

from amaunator.config.logging import get_logger
from amaunator.core.metrics import ACTIVE_TARGETS
from amaunator.core.monitoring import monitor
from amaunator.models import Target, TargetStatus, TargetWithStatus

logger = get_logger(__name__)


class MonitorManager:
    """Manages the lifecycle of monitoring tasks for targets."""

    def __init__(
        self,
        result_queue: asyncio.Queue,
        monitor_func: Callable[[asyncio.Queue, Target, asyncio.Event], Awaitable[None]] = monitor,
    ):
        """
        Initialize the MonitorManager.

        Args:
            result_queue: Queue to send monitoring results to
            monitor_func: Function to use for monitoring. Defaults to the default monitor function.
        """
        self.result_queue = result_queue
        self.tasks: dict[UUID, asyncio.Task] = {}
        self.stop_events: dict[UUID, asyncio.Event] = {}
        self.targets: dict[UUID, Target] = {}  # Source of Truth for Targets
        self.target_statuses: dict[UUID, TargetStatus] = {}
        self.monitor_func = monitor_func
        self.start_time = time.time()

    def get_target(self, target_id: UUID) -> Target | None:
        """Get a target by ID."""
        return self.targets.get(target_id)

    def get_target_with_status(self, target_id: UUID) -> TargetWithStatus | None:
        """Get a target with its status by ID."""
        target = self.targets.get(target_id)
        if not target:
            return None
        status = self.target_statuses.get(target_id, TargetStatus())
        return TargetWithStatus(**target.model_dump(), status=status)

    def get_all_targets(self) -> list[Target]:
        """Get all active targets."""
        return list(self.targets.values())

    def get_all_targets_with_status(self) -> list[TargetWithStatus]:
        """Get all active targets with their status."""
        results = []
        for target in self.targets.values():
            status = self.target_statuses.get(target.id, TargetStatus())
            results.append(TargetWithStatus(**target.model_dump(), status=status))
        return results

    def get_active_count(self) -> int:
        """Get number of active monitoring tasks."""
        return len(self.tasks)

    def update_target_status(self, target_id: UUID, value: int, timestamp: float):
        """Update the status of a target."""
        if target_id not in self.target_statuses:
            self.target_statuses[target_id] = TargetStatus()

        status = self.target_statuses[target_id]
        status.check_count += 1
        status.last_check = timestamp
        status.last_value = value

        if value < 0:  # Error condition
            status.error_count += 1

    def start_monitoring(self, target: Target) -> None:
        """
        Start monitoring a target.

        Args:
            target: The target to monitor
        """
        if target.id in self.tasks:
            logger.warning(f"Monitoring task for target {target.name} (id: {target.id}) already exists")
            return

        # Source of Truth: Store the target definition
        self.targets[target.id] = target
        self.target_statuses[target.id] = TargetStatus()

        # Create stop event for this target
        stop_event = asyncio.Event()
        self.stop_events[target.id] = stop_event

        # Start the monitor task with the event
        task = asyncio.create_task(self.monitor_func(self.result_queue, target, stop_event))
        self.tasks[target.id] = task

        # Update Metrics
        ACTIVE_TARGETS.inc()

        logger.info(f"Started monitoring task for target {target.name} (id: {target.id})")

    def stop_monitoring(self, target_id: UUID) -> None:
        """
        Stop monitoring a target.

        Args:
            target_id: ID of the target to stop monitoring
        """
        if target_id not in self.tasks:
            logger.warning(f"No monitoring task found for target id: {target_id}")
            return

        # Signal the monitor to stop
        if target_id in self.stop_events:
            self.stop_events[target_id].set()
            del self.stop_events[target_id]

        # Clean up task reference
        del self.tasks[target_id]

        # Clean up target definition
        if target_id in self.targets:
            del self.targets[target_id]
        if target_id in self.target_statuses:
            del self.target_statuses[target_id]

        # Update Metrics
        ACTIVE_TARGETS.dec()

        logger.info(f"Stopped monitoring task for target id: {target_id}")

    def stop_all(self) -> None:
        """Stop all monitoring tasks."""
        logger.info(f"Stopping all monitoring tasks ({len(self.tasks)} tasks)")
        for target_id in list(self.tasks.keys()):
            self.stop_monitoring(target_id)
        logger.info("All monitoring tasks stopped")
