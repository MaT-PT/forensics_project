import shutil
import subprocess
from logging import Logger
from typing import overload

SIZE_UNITS = ["B", "K", "M", "G", "T", "P"]
REQUIRED_TOOLS = ["mmls", "fls", "icat"]

TSK_PATH: str | None = None


def pretty_size(size: int, compact: bool = True) -> str:
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
    global TSK_PATH
    TSK_PATH = path


def get_program_path(name: str) -> str:
    res = shutil.which(name, path=TSK_PATH)
    if res is None:
        raise FileNotFoundError(f"{name} not found in {'PATH' if TSK_PATH is None else TSK_PATH}")
    return res


def check_required_tools() -> None:
    for tool in REQUIRED_TOOLS:
        get_program_path(tool)


@overload
def run_program(
    name: str, args: list[str], logger: Logger, encoding: None = ..., can_fail: bool = ...
) -> bytes: ...


@overload
def run_program(
    name: str, args: list[str], logger: Logger, encoding: str, can_fail: bool = ...
) -> str: ...


def run_program(
    name: str,
    args: list[str],
    logger: Logger,
    encoding: str | None = None,
    can_fail: bool = False,
    silent_stderr: bool = False,
) -> str | bytes:
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
