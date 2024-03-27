import logging
from typing import Any

from termcolor import colored

from .termcolor_types import Attribute, Color

LOGLEVEL_COLORS: dict[int, tuple[Color, list[Attribute]]] = {
    logging.DEBUG: ("white", []),
    logging.INFO: ("cyan", []),
    logging.WARNING: ("yellow", []),
    logging.ERROR: ("red", []),
    logging.CRITICAL: ("red", ["bold"]),
}


def init_logging_colors() -> None:
    for level, (color, attrs) in LOGLEVEL_COLORS.items():
        name: str = logging.getLevelName(level)
        logging.addLevelName(level, colored(name, color, attrs=attrs))


def print_log(
    msg: str,
    prefix_char: str = "*",
    color: Color = "cyan",
    attrs: list[Attribute] = [],
    **kwargs: Any,
) -> None:
    print(f"[{colored(prefix_char, color, attrs=attrs)}] {msg}", **kwargs)


def print_info(msg: str, **kwargs: Any) -> None:
    print_log(msg, prefix_char="*", color="cyan", **kwargs)


def print_warning(msg: str, **kwargs: Any) -> None:
    print_log(f"Warning: {msg}", prefix_char="!", color="yellow", **kwargs)


def print_error(msg: str, **kwargs: Any) -> None:
    print_log(f"Error: {msg}", prefix_char="!", color="red", **kwargs)