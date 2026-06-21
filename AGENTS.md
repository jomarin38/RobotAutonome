# Project Agents

Custom agents for code quality analysis and automation.

## structure-auditor

Audits project structure and code coherence.

**Checks:**
- Naming consistency (snake_case throughout)
- Top-down definition order (functions defined before use)
- Comment and docstring quality (up-to-date, purposeful, consistent style)
- Dead code detection (unused variables, imports, commented code)
- User-facing string consistency (logs, error messages, user text)

**Used by:** `cc-audit-structure` workflow

## bug-finder

Detects bugs, logical flaws, and potential issues.

**Categories:**
- Logique — Incorrect conditions, infinite loops, inconsistent state
- Sécurité — Injections, unauthorized access, insufficient validation
- Concurrence — Race conditions, deadlocks, missing synchronization
- Ressources — Memory leaks, unclosed files, released connections
- Type — Type incompatibilities, dangerous conversions
- Erreur Handling — Uncaught exceptions, unerased errors
- Performance — Inefficient algorithms
- Edge Cases — Off-by-one errors, empty containers, None handling

**Output:** Structured report with name, explanation, category, location, fix instructions, and criticality (0-100).

**Used by:** `cc-audit-bugs` workflow

## code-fixer

Applies fixes based on audit results.

**Features:**
- Minimal, targeted corrections
- Maintains project style and conventions
- Respects French comments / English identifiers
- No logic changes or new features

**Used by:** `cc-audit-structure` and `cc-audit-bugs` workflows (with `--fix` flag)
