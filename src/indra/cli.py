from datetime import datetime
from typing import Optional

import typer

from indra.fetch import cds_app, imd_app
from indra.logging_config import configure_logging

# Create the main app
app = typer.Typer(
    name="indra",
    help="CLI tool for fetching and processing weather data",
)

# Create a fetch subcommand group
fetch_app = typer.Typer(
    name="fetch",
    help="Fetch data from various sources",
)

def get_default_log_filename() -> str:
    """Generate default log filename based on timestamp."""
    return f"indra_{datetime.now().strftime('%Y%m%d')}.log"

@app.callback()
def main(
    ctx: typer.Context,
    log_level: str = typer.Option(
        "INFO",
        "--log-level",
        "-l",
        help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    ),
    log_file: Optional[str] = typer.Option(
        None,
        "--log-file",
        "-f",
        help="Custom log filename. If not provided, uses timestamp-based default"
    ),
) -> None:
    """Initialize logging for the entire CLI application."""
    # Ensure we have a context object
    ctx.obj = ctx.obj or {}

    # Generate default log filename if none provided
    if log_file is None:
        log_file = get_default_log_filename()

    # Configure logging
    configure_logging(
        level=log_level,
        log_file=log_file,
        console=True,
        logger_name="indra"
    )

    # Store the logging configuration in the context
    ctx.obj.update({
        "log_level": log_level,
        "log_file": log_file
    })

# Add fetch as a subcommand to main app
app.add_typer(fetch_app, name="fetch")

# Add cds as a subcommand to fetch
fetch_app.add_typer(cds_app, name="cds")
fetch_app.add_typer(imd_app, name="imd")
if __name__ == "__main__":
    app(obj={})
