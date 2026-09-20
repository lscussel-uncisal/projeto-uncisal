# Contributing

## Commit message convention

This repository follows [Conventional Commits v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/).
**Commit messages are always written in English**, regardless of the language used elsewhere in
the project (this document, code comments, and `docs/` are in Portuguese — commit history is not).

### Format

```
<type>(<optional scope>): <short summary, imperative mood, no trailing period>

<optional body — the why, not the what; wrap at ~72 chars>

<optional footer(s) — BREAKING CHANGE:, Refs:, Co-authored-by:, etc.>
```

### Types

| Type | Use for |
|---|---|
| `feat` | A new feature visible to the end user or consumer of the code |
| `fix` | A bug fix |
| `docs` | Documentation only (README, `docs/`, docstrings, comments) |
| `style` | Formatting only — no logic change (whitespace, `black`/`ruff format`) |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `perf` | A change that improves performance |
| `test` | Adding or correcting tests, no production code change |
| `build` | Build system or dependencies (`requirements*.txt`, `Dockerfile`, `pyproject.toml`) |
| `ci` | CI/CD configuration (`.github/workflows/`) |
| `chore` | Everything else that doesn't touch `src/` or tests (tooling, `.gitignore`, etc.) |
| `revert` | Reverts a previous commit |

### Breaking changes

Append `!` after the type/scope, and explain in a `BREAKING CHANGE:` footer:

```
feat(accounts)!: require two-factor confirmation before first login

BREAKING CHANGE: existing sessions created before this change are invalidated.
```

### Scope

Optional, in parentheses after the type. Prefer the app or area touched:
`accounts`, `tickets`, `core`, `infra`, `docker`, `ci`, `docs`.

### Examples from this project

```
feat(accounts): add login lockout after repeated failed attempts

fix(config): require SECRET_KEY in production instead of falling back to
the development default

docs(security): add risk matrix and incident response runbook

build(docker): recompile Tailwind CSS on every image build instead of
relying on the committed file

fix(docker): mount SQLite database inside the persisted volume

  DATABASE_PATH was relative, resolving outside db_data/ inside the
  container — every deploy silently wiped the database.

chore: add gitleaks allowlist for the shared test fixture password
```

### Why Conventional Commits here

- The type alone tells a reviewer (or the professor evaluating this project) what kind of change
  a commit is, without opening the diff.
- It pairs naturally with `docs/architecture/decisions.md`: an ADR explains *why*, the commit that
  implements it explains *what changed*, in the same vocabulary.
- It's the de facto standard used in the industry this project is meant to simulate.

## Pull requests / direct commits to `main`

This is a single-contributor academic project — commits land directly on `main`. The convention
above still applies to every commit, not just ones that go through review.
