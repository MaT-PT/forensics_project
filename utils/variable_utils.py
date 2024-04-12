from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path, PurePath
from typing import Protocol

LOGGER = logging.getLogger(__name__)


class VarFunction(Protocol):
    """Protocol for functions that can be called from a variable substitution in a string."""

    def __call__(self, *args: str) -> str: ...


VAR_FUNCTIONS: dict[str, VarFunction] = {
    "PATH": lambda *args: str(Path(args[0])),
    "REPLACE": lambda *args: args[0].replace(args[1], args[2]),
}


def sub_vars_loop(s: str, var_dict: dict[str, str], upper: bool = True, max_iter: int = 10) -> str:
    """Substitutes variables in a string, repeatedly until no more substitutions are possible."""
    for _ in range(max_iter):
        new_s = s
        for key, value in var_dict.items():
            key = key.removeprefix("$")
            new_s = new_s.replace(f"${key.upper() if upper else key}", value)
        if new_s == s:
            return new_s
        s = new_s
    LOGGER.warning(f"Max number of iterations reached while substituting variables in: {s}")
    return s


def sub_funcs(s: str, upper: bool = True) -> str:
    """Runs functions of the form of `${FUNC_NAME:arg1,arg2,...}`."""
    while True:
        # Find the last function call in the string (to handle nested calls correctly)
        if (start := s.rfind("${")) == -1:
            break
        # Find the corresponding closing bracket
        if (end := s.find("}", start)) == -1:
            LOGGER.warning(f"Unterminated function call: {s[start:]}")
            break
        if ":" not in (func := s[start + 2 : end]):
            LOGGER.warning(f"Invalid function syntax: {func}")
            break
        LOGGER.debug(f"Found function: {func}")
        func_name, args_str = func.split(":")
        if func_name not in VAR_FUNCTIONS:
            LOGGER.warning(f"Unknown function: {func_name}")
        if upper:
            func_name = func_name.upper()
        args = args_str.split(",")
        LOGGER.debug(f"Calling function: {func_name}({args})")
        s = s[:start] + VAR_FUNCTIONS[func_name](*args) + s[end + 1 :]
    return s


def sub_vars(s: str, var_dict: dict[str, str], upper: bool = True, max_iter: int = 10) -> str:
    """Substitutes variables in a string, using a dictionary of variables. Also runs functions.

    Variables are of the form `$VAR_NAME`. Functions are of the form `${FUNC_NAME:arg1,arg2,...}`.

    In addition to the variables in `var_dict`, the following variables are available:
    - `$TIME`: The current time with format `HH.MM.SS`.
    - `$DATE`: The current date with format `YYYY-MM-DD`.
    """
    if "$" not in s:
        return s
    if "TIME" not in var_dict:
        var_dict["TIME"] = datetime.now().strftime("%H.%M.%S")
    if "DATE" not in var_dict:
        var_dict["DATE"] = datetime.now().strftime("%Y-%m-%d")
    return sub_funcs(sub_vars_loop(s, var_dict, upper, max_iter))


def get_username(path: str | PurePath) -> str | None:
    """Gets the username from a path, if applicable.
    For instance, the username is `foo` in the paths
    `\\Users\\foo\\NTUSER.dat` and `/home/foo/.profile`."""
    if isinstance(path, str):
        path = PurePath(path)
    if len(path.parts) > 1 and (path.is_relative_to("Users") or path.is_relative_to("home")):
        return path.parts[1]
    if len(path.parts) > 2 and path.is_relative_to("Windows/ServiceProfiles"):
        return path.parts[2]
    if path.is_relative_to("root"):
        return "root"
    return None
