import logging
import logging.config
import logging.handlers
from pathlib import Path


def configure_logging(
    level: str = "INFO",
    log_file: str | None = None,
    console: bool = True,
    logger_name: str = "indra",
) -> None:
    """Configure logging for both CLI and SDK usage.

    :param level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    :param log_file: Optional file path for logging. If None, only console logging is used
    :param console: Whether to enable console logging
    :param logger_name: Name of the logger to configure
    """
    # Ensure valid logging level
    level = level.upper()
    if level not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
        raise ValueError(f"Invalid logging level: {level}")

    # Basic config with formatter
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            },
        },
        'handlers': {},
        'loggers': {
            # Root logger
            '': {
                'handlers': [],
                'level': 'WARNING',  # Default level for root
                'propagate': True,
            },
            # Named logger
            logger_name: {
                'handlers': [],
                'level': level,
                'propagate': False,  # Don't propagate to root
            }
        }
    }

    # Add console handler if requested
    if console:
        config['handlers']['console'] = {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
            'level': level,
        }
        config['loggers'][logger_name]['handlers'].append('console')

    # Add file handler if log_file is specified
    if log_file:
        # Ensure logs directory exists
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        file_path = log_dir / log_file
        config['handlers']['file'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'standard',
            'filename': str(file_path),
            'mode': 'a',
            'maxBytes': 10_485_760,  # 10MB
            'backupCount': 5,
            'level': level,
        }
        config['loggers'][logger_name]['handlers'].append('file')

    # Apply configuration
    logging.config.dictConfig(config)

    # Capture warnings
    logging.captureWarnings(True)

    return logging.getLogger(logger_name)

__all__ = ['configure_logging']
