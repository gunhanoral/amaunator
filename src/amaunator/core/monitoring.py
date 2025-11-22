import asyncio
import contextlib
import functools
from collections.abc import AsyncGenerator, Awaitable, Callable
from random import randint

from amaunator.config.logging import get_logger
from amaunator.models import Target, TargetResult

logger = get_logger(__name__)

# Type hint for poll functions
PollFunction = Callable[[Target], Awaitable[int]]


def periodic_task(interval_attr: str = "interval"):
    """
    Decorator to turn an async generator into a precise periodic task.
    Handles drift correction, graceful shutdown, and error suppression.

    Args:
        interval_attr: Name of the attribute on the first argument (e.g., target.interval)
                       to use for the loop interval.
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(target: Target, stop_event: asyncio.Event, *args, **kwargs):
            # Get interval from the target object
            interval = getattr(target, interval_attr)

            # Drift Correction Setup
            loop = asyncio.get_running_loop()
            next_run_time = loop.time()

            while not stop_event.is_set():
                # 1. Calculate drift-corrected sleep time
                now = loop.time()
                delay = max(0, next_run_time - now)

                # 2. Smart Wait: Wait for 'delay' seconds OR until 'stop_event' is set
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop_event.wait(), timeout=delay)

                if stop_event.is_set():
                    logger.info(f"Stop signal received for {func.__name__}. Exiting loop.")
                    break

                # 3. Run the Business Logic (Yield results)
                try:
                    # We iterate over the generator (which should yield one or more results per cycle)
                    async for item in func(target, stop_event, *args, **kwargs):
                        yield item
                except Exception as e:
                    logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
                    # Prevent tight loop on persistent error
                    if not stop_event.is_set():
                        await asyncio.sleep(1)

                # 4. Schedule next run
                next_run_time += interval

        return wrapper

    return decorator


# mock poll function
async def poll(target: Target) -> int:
    """Default mock poll function"""
    try:
        # TimeoutError is raised by the context manager exit, not inside the block
        async with asyncio.timeout(target.timeout):
            await asyncio.sleep(randint(1, round(target.timeout * 1.2)))
            return randint(0, 100)
    except TimeoutError:
        logger.warning(f"Poll timeout for target {target.name} (id: {target.id})")
        return -1
    except Exception as e:
        logger.error(f"Poll failed for target {target.name}: {e}")
        return -1


@periodic_task(interval_attr="interval")
async def monitor_stream(
    target: Target,
    stop_event: asyncio.Event,  # Required by signature but unused in simple poll
    poll_func: PollFunction = poll,
) -> AsyncGenerator[dict]:
    """
    Yields monitoring results periodically.
    The @periodic_task decorator handles the timing and loop.
    """
    _ = stop_event  # Silence unused variable warning
    result = await poll_func(target)
    result_data = TargetResult(target_id=target.id, value=result).model_dump()
    yield result_data


async def monitor(
    queue: asyncio.Queue,
    target: Target,
    stop_event: asyncio.Event,
    poll_func: PollFunction = poll,
):
    """
    Consumer that reads from the monitor stream and puts results in the queue.
    """
    logger.info(f"Starting monitoring for target {target.name} (id: {target.id}, interval: {target.interval}s)")

    # Consume the stream
    async for result_data in monitor_stream(target, stop_event, poll_func=poll_func):
        await queue.put(result_data)
        logger.debug(f"Queued result for target {target.name} (id: {target.id}): {result_data}")
