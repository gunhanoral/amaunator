# Amaunator

Amaunator is a lightweight, asynchronous monitoring daemon built with Python. It allows you to schedule monitoring tasks (targets), collect results, and output them to various destinations (Console, File). It includes a REST API for managing targets and viewing system statistics, as well as a Prometheus metrics endpoint.

## Features

- **Async Architecture**: Built on `asyncio` for efficient concurrent monitoring.
- **Dynamic Target Management**: Add or remove monitoring targets at runtime via REST API.
- **Pluggable Outputs**: Currently supports logging to Console or File (with rotation).
- **REST API**: FastAPI-powered interface to interact with the daemon.
- **Observability**:
  - `/stats` endpoint for internal system statistics.
  - `/metrics` endpoint for Prometheus integration.

## Requirements

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) (Recommended for dependency management)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/amaunator.git
   cd amaunator
   ```

2. Install dependencies:
   ```bash
   uv sync
   ```

## Usage

### Running the Daemon

You can run the daemon directly using `uv`:

```bash
# Ensure src is in python path if not installed as package
PYTHONPATH=src uv run src/amaunator/main.py
```

Or if installed in editable mode:

```bash
uv pip install -e .
uv run src/amaunator/main.py
```

The server will start on `http://0.0.0.0:8000` by default.

### Configuration

Configuration is handled via `config.yaml` (not committed by default) or defaults. The application uses `pydantic-settings`.

**Example `config.yaml`:**

```yaml
log_level: INFO
api:
  host: "0.0.0.0"
  port: 8000
output:
  type: "file"
  path: "logs/monitor.log"
  max_bytes: 10485760
  backup_count: 5
```

Supported output types: `console`, `file`.

## API Endpoints

### Targets

- **GET /targets**: List all active targets.
- **POST /targets**: Add a new target.
- **GET /targets/{id}**: Get details for a specific target.
- **DELETE /targets/{id}**: Stop and remove a target.

**Add Target Example:**

```bash
curl -X POST http://localhost:8000/targets \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Check Service A",
    "interval": 5,
    "timeout": 2
  }'
```

### Monitoring & Stats

- **GET /stats**: System-wide statistics (uptime, active targets, queue size, etc.).
- **GET /metrics**: Prometheus metrics endpoint.

**Metrics Exposed:**
- `amaunator_active_targets`: Number of currently active monitoring targets.
- `amaunator_processed_messages_total`: Total processed results.
- `amaunator_target_value`: Current value of a target.
- `amaunator_processing_errors_total`: Error counts.
- `amaunator_queue_size`: Current internal queue size.

## Development

### Project Structure

- `src/amaunator/api`: FastAPI routes and API logic.
- `src/amaunator/core`: Core logic (MonitorManager, Monitoring loops).
- `src/amaunator/config`: Configuration and logging setup.
- `src/amaunator/outputs`: Output processors and handlers.

### Running Tests

```bash
uv run pytest
```

