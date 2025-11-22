import asyncio
import contextlib
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from amaunator.config.logging import get_logger
from amaunator.config.settings import settings
from amaunator.core.manager import MonitorManager
from amaunator.core.metrics import (
    PROCESSED_MESSAGES,
    PROCESSING_ERRORS,
    QUEUE_SIZE,
    TARGET_VALUE,
)
from amaunator.models import TargetResult

logger = get_logger(__name__)


class OutputHandler(ABC):
    """Base class for output handlers."""

    @abstractmethod
    async def handle(self, target_result: TargetResult, target_name: str | None) -> None:
        """
        Handle a monitoring result.

        Args:
            target_result: The result to output
            target_name: Name of the target (if found)
        """
        pass


class ConsoleOutputHandler(OutputHandler):
    """Output handler that writes to console via logger."""

    async def handle(self, target_result: TargetResult, target_name: str | None) -> None:
        if target_name:
            logger.info(f"Output: {target_result.value} for target {target_name} (id: {target_result.target_id})")
        else:
            logger.warning(f"Output: {target_result.value} for unknown target (id: {target_result.target_id})")


class FileOutputHandler(OutputHandler):
    """Output handler that writes to a file with rotation."""

    def __init__(
        self,
        file_path: str,
        format_string: str = "{timestamp} - {target_name} - {value}",
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
    ):
        """
        Initialize the file output handler.

        Args:
            file_path: Path to the output file
            format_string: Format string for output lines
            max_bytes: Maximum file size before rotation
            backup_count: Number of backup files to keep
        """
        self.file_path = Path(file_path)
        self.format_string = format_string
        self.max_bytes = max_bytes
        self.backup_count = backup_count

        # Create parent directory if it doesn't exist
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def _rotate_file(self) -> None:
        """Rotate the log file if it exceeds max_bytes."""
        if not self.file_path.exists():
            return

        if self.file_path.stat().st_size >= self.max_bytes:
            # Rotate existing backup files
            for i in range(self.backup_count - 1, 0, -1):
                old_file = self.file_path.with_suffix(f".{i}")
                new_file = self.file_path.with_suffix(f".{i + 1}")
                if old_file.exists():
                    old_file.replace(new_file)

            # Move current file to .1
            backup_file = self.file_path.with_suffix(".1")
            self.file_path.replace(backup_file)

    async def handle(self, target_result: TargetResult, target_name: str | None) -> None:
        # Check if rotation is needed
        self._rotate_file()

        # Format the output line
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = self.format_string.format(
            timestamp=timestamp,
            target_name=target_name or "unknown",
            target_id=target_result.target_id,
            value=target_result.value,
        )

        # Write to file
        with self.file_path.open("a") as f:
            f.write(line + "\n")


class OutputProcessor:
    """Processes items from the queue and sends them to the handler."""

    def __init__(
        self,
        queue: asyncio.Queue,
        handler: OutputHandler,
        monitor_manager: MonitorManager,
    ):
        self.queue = queue
        self.handler = handler
        self.monitor_manager = monitor_manager
        self.processed_count = 0
        self.error_count = 0
        self.stop_event = asyncio.Event()

    async def run(self) -> None:
        """Run the processor loop."""
        handler_name = self.handler.__class__.__name__
        logger.info(f"Output processor started with {handler_name}")

        while not self.stop_event.is_set():
            # Wait for item OR stop event
            try:
                # Update queue size metric
                QUEUE_SIZE.set(self.queue.qsize())

                # Create a task for getting the item
                get_task = asyncio.create_task(self.queue.get())
                stop_task = asyncio.create_task(self.stop_event.wait())

                # Wait for the get task OR the stop event
                done, pending = await asyncio.wait(
                    [get_task, stop_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                # Cancel pending tasks (whichever didn't finish)
                for task in pending:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task

                if self.stop_event.is_set():
                    break

                # If we got here, the queue has an item (get_task finished)
                result = await get_task
                target_result = TargetResult.model_validate(result)

                # Find target name using the injected manager
                target = self.monitor_manager.get_target(target_result.target_id)
                target_name = target.name if target else "unknown"
                target_id_str = str(target_result.target_id)

                # Update status in manager
                self.monitor_manager.update_target_status(
                    target_result.target_id, target_result.value, target_result.timestamp
                )

                # Handle the result
                await self.handler.handle(target_result, target_name)

                # Update stats and metrics
                self.processed_count += 1
                PROCESSED_MESSAGES.inc()
                TARGET_VALUE.labels(target_name=target_name, target_id=target_id_str).set(target_result.value)

                self.queue.task_done()
            except Exception as e:
                self.error_count += 1
                PROCESSING_ERRORS.inc()
                logger.error(f"Error processing output queue: {e}", exc_info=True)

        logger.info("Output processor stopped")


def create_output_handler() -> OutputHandler:
    """
    Create an output handler based on settings.

    Returns:
        OutputHandler instance based on configuration
    """
    output_config = settings.output

    if output_config.type == "console":
        return ConsoleOutputHandler()
    elif output_config.type == "file":
        if not output_config.file_path:
            logger.warning("File output type selected but no file path provided, falling back to console")
            return ConsoleOutputHandler()
        return FileOutputHandler(
            file_path=output_config.file_path,
            format_string=output_config.file_format,
            max_bytes=output_config.file_max_bytes,
            backup_count=output_config.file_backup_count,
        )
    else:
        logger.warning(f"Unknown output type: {output_config.type}, falling back to console")
        return ConsoleOutputHandler()
