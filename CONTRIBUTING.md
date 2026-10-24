# Contributing

## Set up

Follow "Install for development" and "Test" in the [README](README.md).
You need PostgreSQL and Redis running, and a `DATABASE_URL` that points at a database the tests may wipe.

Install the git hooks once.

```bash
uv run pre-commit install
```

The hooks run ruff lint, ruff format and mypy before each commit.

## Make a change

1. Branch from `main`.
2. Write the change and the tests that prove it in the same commit.
   A bug fix starts with a test that fails on the old code.
3. Run the same checks CI runs.

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run alembic check
uv run pytest --cov=app
```

4. Open a pull request against `main`.
   CI must pass before merge.

## Commit messages

Use Conventional Commits, with a scope that names the area you changed.

```
fix(trending): bucket synced posts by UTC, not host local time
```

The types in use are `feat`, `fix`, `refactor`, `test`, `docs`, `build`, `ci`, `style` and `chore`.
Put the reason for the change in the body when the subject cannot carry it.

## Dependencies

`pyproject.toml` pins every direct dependency to an exact version, and `uv.lock` locks the whole tree.

```bash
uv add <package>==<version>          # runtime
uv add --group dev <package>==<version>
```

Then regenerate the pip requirements files so they match the lock.

```bash
uv export --frozen --no-dev --no-hashes --no-emit-project -o requirements.txt
uv export --frozen --only-group dev --no-hashes --no-emit-project -o requirements-dev.txt
```

CI fails when `uv.lock` is out of date with `pyproject.toml`, or when `pip-audit` finds a known vulnerability.

## Database changes

Change the models in `app/models.py`, then generate a migration and read it before you commit it.

```bash
uv run alembic revision --autogenerate -m "short description"
uv run alembic upgrade head
uv run alembic check
```

`alembic check` must report no new operations.
CI runs it after migrating, so a model change without its migration fails the build.

## Logging

Get a logger with `logging.getLogger(__name__)` and pass context through `extra=`.
Each `extra` key becomes a field in the JSON log line.
Do not use `print` outside the CLI's user-facing output.
