"""Process module — spatial interpolation and data transformation pipelines."""

import typer

app = typer.Typer(
    name="process",
    help="Process and transform weather data (CoS, analysis, etc.)",
)


def _register_commands() -> None:
    """Lazy-import subcommands to avoid circular imports.

    Called after ``app`` is defined, so ``cos.py`` can import ``app``
    from this module without circular dependency issues.
    """
    from indra.process import cos  # noqa: F401


_register_commands()

__all__ = ["app"]
