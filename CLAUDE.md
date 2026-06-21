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
uv run robot-autonome

# Type-check
uv run mypy src/

# Install dependencies
uv sync
```

There are no tests at this time.

## Custom Skills

### Manual Invocation Skills
Invoke with `/skill-name` in the chat:

**Code Quality & Audits**
```
/cc-audit-structure [--fix]    # Audit structure, naming, order, comments, dead code
/cc-audit-bugs [--fix]         # Detect bugs and generate categorized report
/cc-audit-full [--fix]         # Complete audit (structure + bugs + report)
```

**Documentation**
```
/doc-writer [--update]         # Write/update project documentation and docstrings
/readme-writer [--create]      # Write/update README.md with complete structure
```

**Skill Authoring**
```
/skill-creator                 # Interactive guide to create skills and agents
```

### Auto-Invocation Skills
Automatically invoked by Claude when needed:
- `git-ops` — Git operations (merge, rebase, branch management)
- `shell-exec` — Shell commands and scripts execution
- `diagnose` — System monitoring and performance diagnostics
- `devtools` — Package managers, build systems, CI/CD
- `linux-terminal` — Coordinator for complex terminal workflows

## Available Agents (14 agents)

14 specialized agents for analysis and optimization tasks:

### 🔍 Exploration
- `explorer-global` — Project architecture overview
- `explorer-precise` — Targeted code search

### 🐍 Python & Performance
- `python-optimizer` — Code optimization (algorithms, memory, I/O)
- `python-refactorer` — Refactoring and maintainability
- `python-type-expert` — Advanced typing (type hints, generics)
- `performance-profiler` — Profiling, benchmarking

### 🏗️ Architecture & API
- `architecture-reviewer` — Architectural review (SOLID, patterns)
- `api-designer` — REST/gRPC API design with OpenAPI

### 🔒 Quality & Security
- `security-auditor` — Security audit (OWASP Top 10)
- `bug-finder` — Bug detection (logic, concurrency, resources)
- `test-engineer` — Unit tests, coverage
- `structure-auditor` — Code coherence audit

### 📚 Documentation & Infrastructure
- `documentation-writer` — Docstrings, guides, API documentation
- `code-fixer` — Apply fixes from audit results

Agents are parallelizable or perform subtasks completely different from the main task.

## Rules for Claude Code

1. **Never commit without explicit authorization** — Always ask for permission before running `git commit`, `git push`, or any destructive git operations.
2. **Do not modify code without being asked** — Only write code when explicitly requested by the user.
3. **Follow project code style** — All code must follow the existing style and conventions of this project.

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
