import logging
from os import environ
from sys import exit, platform
from typing import Any, NoReturn, overload

from termcolor import colored
from termcolor._types import Attribute, Color

LOGLEVEL_COLORS: dict[int, tuple[Color, list[Attribute]]] = {
    logging.DEBUG: ("white", []),
    logging.INFO: ("cyan", []),
    logging.WARNING: ("yellow", []),
    logging.ERROR: ("red", []),
    logging.CRITICAL: ("red", ["bold"]),
}


def init_logging_colors() -> None:
    """Initializes terminal colors with colorama if necessary
    and sets up logging levels with colors."""
    if platform == "win32" and "WT_SESSION" not in environ:
        try:
            from colorama import just_fix_windows_console

            just_fix_windows_console()
        except ImportError:
            environ["NO_COLOR"] = "1"
            print_warning("Colorama not installed, colors will not work on Windows legacy console.")
            print("    Consider installing it with 'pip install colorama'.")

    for level, (color, attrs) in LOGLEVEL_COLORS.items():
        name: str = logging.getLevelName(level)
        logging.addLevelName(level, colored(name, color, attrs=attrs))


def print_log(
    msg: str,
    /,
    *,
    prefix_char: str = "*",
    color: Color = "cyan",
    attrs: list[Attribute] = [],
    **kwargs: Any,
) -> None:
    print(f"[{colored(prefix_char, color, attrs=attrs)}] {msg}", **kwargs)


def print_info(msg: str, /, **kwargs: Any) -> None:
    print_log(msg, prefix_char="*", color="cyan", **kwargs)


def print_warning(msg: str, /, **kwargs: Any) -> None:
    print_log(f"Warning: {msg}", prefix_char="!", color="yellow", **kwargs)


@overload
def print_error(msg: str, /, *, exit_code: int, **kwargs: Any) -> NoReturn: ...
@overload
def print_error(msg: str, /, *, exit_code: None = ..., **kwargs: Any) -> None: ...


def print_error(msg: str, /, *, exit_code: int | None = None, **kwargs: Any) -> None:
    print_log(f"Error: {msg}", prefix_char="!", color="red", **kwargs)
    if exit_code is not None:
        exit(exit_code)
