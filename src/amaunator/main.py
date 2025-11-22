import asyncio
import contextlib
import logging
import signal

from fastapi import FastAPI
from uvicorn import Config, Server

from amaunator.api.routes import router
from amaunator.config.logging import setup_logging
from amaunator.config.settings import settings
from amaunator.core.manager import MonitorManager
from amaunator.outputs import OutputProcessor, create_output_handler

# Set up logging with configured level
setup_logging(log_level=settings.log_level)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Amaunator Monitoring Service")
app.include_router(router)


async def main():
    """
    Main daemon entry point.
    Orchestrates the MonitorManager, OutputProcessor, and API Server.
    """
    logger.info("Starting Amaunator Daemon...")

    # 1. Initialize Core Components
    result_queue = asyncio.Queue()
    monitor_manager = MonitorManager(result_queue)
    output_handler = create_output_handler()
    output_processor = OutputProcessor(result_queue, output_handler, monitor_manager)

    # 2. Inject Core into API
    # This allows the API to control the manager and read stats from the processor
    app.state.monitor_manager = monitor_manager
    app.state.output_processor = output_processor

    # 3. Setup Tasks
    tasks = []

    # Task: Output Processor
    output_task = asyncio.create_task(output_processor.run(), name="output_processor")
    tasks.append(output_task)

    # Task: API Server
    # We run Uvicorn in a task so it doesn't block our main loop
    config = Config(app, host=settings.api.host, port=settings.api.port, log_config=None)
    server = Server(config)
    server_task = asyncio.create_task(server.serve(), name="api_server")
    tasks.append(server_task)

    # 4. Handle Signals for Graceful Shutdown
    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def signal_handler():
        logger.info("Received shutdown signal")
        shutdown_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    # 5. Run Forever (until signal)
    logger.info("Daemon started. Waiting for signal...")
    await shutdown_event.wait()

    # 6. Graceful Shutdown Sequence
    logger.info("Shutting down...")

    # Stop API first (stop accepting new requests)
    server.should_exit = True
    await server_task

    # Stop Monitoring (Stop producers)
    monitor_manager.stop_all()

    # Stop Output (Stop consumer)
    # Wait for queue to drain? Ideally yes.
    if not result_queue.empty():
        logger.info(f"Draining {result_queue.qsize()} items from queue...")
        await result_queue.join()

    # Signal output processor to stop using the event
    output_processor.stop_event.set()
    await output_task

    logger.info("Shutdown complete.")


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        # We use asyncio.run which creates a new event loop
        asyncio.run(main())
