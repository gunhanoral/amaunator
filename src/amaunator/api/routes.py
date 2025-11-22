import time
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from amaunator.config.logging import get_logger
from amaunator.core.manager import MonitorManager
from amaunator.models import SystemStats, Target, TargetCreate, TargetWithStatus
from amaunator.outputs import OutputProcessor

logger = get_logger(__name__)

router = APIRouter()


def get_manager(request: Request) -> MonitorManager:
    """Helper to get the monitor manager from app state."""
    return request.app.state.monitor_manager


def get_processor(request: Request) -> OutputProcessor:
    """Helper to get the output processor from app state."""
    return request.app.state.output_processor


@router.post("/targets", response_model=Target, status_code=status.HTTP_201_CREATED)
async def add_target(target_in: TargetCreate, request: Request) -> Target:
    """
    Add a new monitoring target.
    """
    manager = get_manager(request)

    # Create internal Target object (generates ID)
    target = Target(**target_in.model_dump())

    # Start monitoring
    manager.start_monitoring(target)

    return target


@router.get("/targets", response_model=list[TargetWithStatus])
async def list_targets(request: Request) -> list[TargetWithStatus]:
    """
    List all active monitoring targets with their status.
    """
    manager = get_manager(request)
    return manager.get_all_targets_with_status()


@router.get("/targets/{target_id}", response_model=TargetWithStatus)
async def get_target(target_id: UUID, request: Request) -> TargetWithStatus:
    """
    Get details of a specific target with its status.
    """
    manager = get_manager(request)
    target = manager.get_target_with_status(target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    return target


@router.delete("/targets/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_target(target_id: UUID, request: Request) -> None:
    """
    Stop monitoring and remove a target.
    """
    manager = get_manager(request)

    # Check if exists first
    if not manager.get_target(target_id):
        raise HTTPException(status_code=404, detail="Target not found")

    manager.stop_monitoring(target_id)
    return None


@router.get("/stats", response_model=SystemStats)
async def get_stats(request: Request) -> SystemStats:
    """
    Get system statistics.
    """
    manager = get_manager(request)
    processor = get_processor(request)

    uptime = time.time() - manager.start_time

    return SystemStats(
        active_targets=manager.get_active_count(),
        processed_messages=processor.processed_count,
        uptime_seconds=uptime,
        queue_size=processor.queue.qsize(),
        total_errors=processor.error_count,
    )


@router.get("/metrics")
async def get_metrics():
    """
    Get Prometheus metrics.
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
