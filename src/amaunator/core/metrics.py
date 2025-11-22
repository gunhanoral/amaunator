from prometheus_client import Counter, Gauge, Histogram

# Metrics definitions
ACTIVE_TARGETS = Gauge("amaunator_active_targets", "Number of currently active monitoring targets")
PROCESSED_MESSAGES = Counter("amaunator_processed_messages_total", "Total number of processed monitoring results")
TARGET_VALUE = Gauge(
    "amaunator_target_value",
    "Current value of a monitoring target",
    ["target_name", "target_id"],
)
PROCESSING_ERRORS = Counter("amaunator_processing_errors_total", "Total number of errors during processing")
QUEUE_SIZE = Gauge("amaunator_queue_size", "Current size of the result queue")

# Optional: Histogram for processing latency if we track it
PROCESSING_TIME = Histogram("amaunator_processing_seconds", "Time spent processing a result")
