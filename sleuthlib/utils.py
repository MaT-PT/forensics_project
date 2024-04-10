import shutil
import subprocess
from logging import Logger
from sys import exit
from typing import overload

SIZE_UNITS = ["B", "K", "M", "G", "T", "P"]
REQUIRED_TOOLS = ["mmls", "fls", "icat"]

TSK_PATH: str | None = None
"""The path to The Sleuth Kit tools."""


def pretty_size(size: int, compact: bool = True) -> str:
    """Converts a size in bytes to a human-readable string.

    Args:
        size: The size in bytes.
        compact: Whether to use compact notation (e.g. "8K" instead of "8 KB").
    """
    if compact:
        units = SIZE_UNITS
    else:
        units = [f" {unit}{'B' if unit != 'B' else ''}" for unit in SIZE_UNITS]

    unit = units[0]
    for unit in units:
        if size < 1024:
            break
        size //= 1024
    return f"{size}{unit}"


def set_tsk_path(path: str | None) -> None:
    """Sets the path to The Sleuth Kit tools."""
    global TSK_PATH
    TSK_PATH = path


def get_program_path(name: str) -> str:
    """Returns the path to the given program, or raises an exception if it's not found.
    Searches in the PATH environment variable or in the TSK_PATH directory, if set."""
    if (path := shutil.which(name, path=TSK_PATH)) is None:
        raise FileNotFoundError(f"{name} not found in {'PATH' if TSK_PATH is None else TSK_PATH}")
    return path


def check_required_tools() -> None:
    """Checks if the required tools are available in TSK_PATH or PATH
    (required tools are `mmls`, `fls`, and `icat`)."""
    for tool in REQUIRED_TOOLS:
        get_program_path(tool)


@overload
def run_program(
    name: str, args: list[str], logger: Logger, encoding: str, can_fail: bool = ...
) -> str:
    """Runs a program with the given arguments. Executable is searched in TSK_PATH or PATH.
    Returns the output of the program as a string, decoded with the given encoding.

    Args:
        name: The name of the program.
        args: The arguments to pass to the program.
        logger: The logger to use.
        encoding: The encoding to use for the output.
        can_fail: Whether the program can fail without raising an exception.
        silent_stderr: Whether to suppress stderr output.
    """


@overload
def run_program(
    name: str, args: list[str], logger: Logger, encoding: None = ..., can_fail: bool = ...
) -> bytes:
    """Runs a program with the given arguments. Executable is searched in TSK_PATH or PATH.
    Returns the raw bytes output of the program.

    Args:
        name: The name of the program.
        args: The arguments to pass to the program.
        logger: The logger to use.
        encoding: None (returns raw bytes).
        can_fail: Whether the program can fail without raising an exception.
        silent_stderr: Whether to suppress stderr output.
    """


def run_program(
    name: str,
    args: list[str],
    logger: Logger,
    encoding: str | None = None,
    can_fail: bool = False,
    silent_stderr: bool = False,
) -> str | bytes:
    """Runs a program with the given arguments. Executable is searched in TSK_PATH or PATH.

    Args:
        name: The name of the program.
        args: The arguments to pass to the program.
        logger: The logger to use.
        encoding: The encoding to use for the output (if None, returns raw bytes).
        can_fail: Whether the program can fail without raising an exception.
        silent_stderr: Whether to suppress stderr output.
    """
    try:
        logger.debug(f"Running {name} {' '.join(args)}")
        exec_path = get_program_path(name)
        res = subprocess.check_output(
            [exec_path] + args,
            encoding=encoding,
            stderr=subprocess.DEVNULL if silent_stderr else None,
        )
        if isinstance(res, bytes):
            logger.debug(f"{name} returned {len(res)} bytes")
        else:
            logger.debug(f"{name} returned: {res}")
        return res
    except subprocess.CalledProcessError as e:
        if can_fail:
            logger.debug(f"{name} failed: {e}")
            raise ChildProcessError(str(e))
        logger.critical(f"Error running {name}: {e}")
        exit(e.returncode)
