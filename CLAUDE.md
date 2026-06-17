# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Language Rules

- **Always communicate in French** — all responses, explanations, and comments must be in French.
- **Write code in English, comments in French** — identifiers, variable names, function names, and string literals should be in English, but all inline comments and docstrings must be written in French.

## Project Overview

Python 3.13 autonomous robot control system for a robotics club. Supports both a Pygame-based simulator and real hardware via serial/I2C. Uses UV as the package manager.

## Commands

```bash
# Run the project
uv run main.py

# Type-check
uv run mypy main.py simulateur.py trajectoryCalculator.py rcControl.py utils/

# Install dependencies
uv sync
```

There are no tests at this time.

## Architecture

The system runs three coordinated processes managed by `main.py`:

1. **Trajectory Calculator** (`trajectoryCalculator.py`) — Computes movement commands to reach a target position. Uses Numba JIT-compiled core math for performance. Reads robot pose from Redis, writes timed command buffers (forward/translate/rotate axes).

2. **RC Control** (`rcControl.py`) — Executes commands on either the simulator or hardware. Writes updated robot position back to Redis, closing the control loop.

3. **Logger process** — Aggregates log messages from all processes via a multiprocessing Queue.

**Data flow**: Target position → Trajectory Calculator → `AllCommandBuffers` → RC Control → Robot/Simulator → Redis (pose) → Trajectory Calculator

### IPC & Shared State

`main.py` creates shared structures via `mp.Manager()`:
- `DictProxy` for robot pose (Redis-backed too)
- `Queue` for log messages
- `Lock` for synchronization

Redis also serves as a secondary pose store for cross-process access.

### Environment Abstraction

`EnvHandler` enum (in `utils/utils.py`) switches behavior across three modes:
- **SIM** — Pygame simulator (`simulateur.py`)
- **SERIAL** — Real hardware via pyserial
- **I2C** — Not yet implemented

Handlers use Python `singledispatch` for polymorphic dispatch: `TargetHandler`, `RobotPosHandler`, `ControlHandler` each have environment-specific implementations.

### Key Files

| File | Role |
|------|------|
| `main.py` | Entry point; spawns and coordinates the three processes |
| `simulateur.py` | Pygame simulator with physics and rendering |
| `trajectoryCalculator.py` | Trajectory generation with Numba JIT |
| `rcControl.py` | Command execution layer |
| `utils/utils.py` | Core dataclasses, logging, polymorphic handlers, Redis integration |
| `utils/config_manager.py` | Pydantic-validated YAML config loader |
| `config.yml` | Runtime config (Redis, serial port, sim window, physics coefficients) |

### Core Data Structures

Defined in `utils/utils.py`, all frozen dataclasses:

```python
Position(x, y, direction)
Command(forward, translate, rotate)
CommandBufferItem(finish_time, command)
AllCommandBuffers(forward, translate, rotate)
Observation(robot_position, target_point)
```

### Configuration (`config.yml`)

Key sections: `redis`, `serial`, `sim` (window size, tick rate, start position), `movement_coeff` (physics coefficients per axis), `inertie_factor` (damping), `utils.logger`, `others` (position buffer length).
