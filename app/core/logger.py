import logging
import sys

from app.core.config import settings


def setup_logger() -> None:
    logging.basicConfig(
        level=logging.DEBUG if settings.DEBUG else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )


setup_logger()


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
