from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass, field
from graphlib import TopologicalSorter
from pathlib import Path, PurePath
from typing import Any, Iterable, Iterator, TypedDict, overload

import yaml

from .colored_logging import print_error
from .config_parser import Config
from .variable_utils import get_username, sub_vars

if sys.version_info >= (3, 11):
    from typing import NotRequired, Self
else:
    from typing_extensions import NotRequired, Self

LOGGER = logging.getLogger(__name__)


@dataclass
class MutableBool:
    """Represents a mutable boolean value. Use `set` to set it to `True` and `reset` for `False`."""

    value: bool = False

    def __bool__(self) -> bool:
        return self.value

    def set(self) -> None:
        self.value = True

    def reset(self) -> None:
        self.value = False

    def __hash__(self) -> int:
        return hash(self.value)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, MutableBool):
            return self.value == other.value
        return self.value == other


@dataclass(frozen=True)
class FileList:
    """List of files and tools to run on them, parsed from a YAML file.
    Use `FileList.from_yaml_file` to parse a YAML file and return a `FileList` instance."""

    files: list[File]
    config: Config

    class YamlFilesOutput(TypedDict):
        """YAML dict: Output file configuration for a tool."""

        path: str
        append: NotRequired[bool]
        stderr: NotRequired[bool]

    class YamlFilesTool(TypedDict):
        """YAML dict: Tool configuration."""

        name: NotRequired[str]
        cmd: NotRequired[str]
        extra: NotRequired[dict[str, Any]]
        filter: NotRequired[str]
        output: NotRequired[str | FileList.YamlFilesOutput]
        requires: NotRequired[list[str]]
        allow_fail: NotRequired[bool]
        run_once: NotRequired[bool]

    class YamlFilesFile(TypedDict):
        """YAML dict: File configuration with path and optional tool(s)."""

        path: str
        tool: NotRequired[FileList.YamlFilesTool]
        tools: NotRequired[list[FileList.YamlFilesTool]]
        overwrite: NotRequired[bool]

    class YamlFiles(TypedDict):
        """YAML dict: Top-level configuration with file list."""

        files: list[str | FileList.YamlFilesFile]

    @dataclass(frozen=True)
    class Tool:
        """Tool to run on a file, with either a command or a reference to a tool in the config.
        Use `Tool.from_dict` to parse a dict and return a `Tool` instance."""

        file: FileList.File = field(repr=False)
        cmd: str | None = None
        name: str | None = None
        extra: dict[str, Any] = field(default_factory=dict)
        filter: str | None = None
        output: Output | None = None
        requires: frozenset[str] = field(default_factory=frozenset)
        allow_fail: bool | None = None
        run_once: bool = False
        _has_run: MutableBool = field(default_factory=MutableBool, init=False, compare=False)

        @dataclass(frozen=True)
        class Output:
            """Output file configuration for a tool.
            Use `Output.from_dict` to create an `Output` instance from a dict or string.

            Attributes:
                path: The path to the output file.
                append: Whether to append to the output file (default: False).
                stderr: Whether to redirect STDERR to the output file (default: False).
            """

            path: str
            append: bool = False
            stderr: bool = False

            @classmethod
            def from_dict(cls, data: FileList.YamlFilesOutput | str | Any) -> Self:
                """Creates an `Output` instance from a dict or string.
                If a string is provided, it is assumed to be a path to the output file."""
                if isinstance(data, str):
                    return cls(path=data)
                if not (isinstance(data, dict) and "path" in data):
                    raise KeyError("Missing 'path' key")
                return cls(
                    path=data["path"],
                    append=bool(data.get("append", False)),
                    stderr=bool(data.get("stderr", False)),
                )

        @classmethod
        def from_dict(cls, data: FileList.YamlFilesTool | Any, file: FileList.File) -> Self:
            """Creates a `Tool` instance from a dict or string.
            If a string is provided, it is assumed to be a command,
            and all other attributes are set to `None`, `False`, or empty sequences."""
            if isinstance(data, str):
                return cls(cmd=data, file=file)
            if not isinstance(data, dict):
                raise TypeError("Invalid tool configuration (must be a string or a dict)")
            name = data.get("name")
            cmd = data.get("cmd")
            if (name is None) == (cmd is None):
                raise ValueError("Must specify either 'name' or 'cmd' key, but not both")
            output = data.get("output")
            return cls(
                name=name,
                file=file,
                cmd=cmd,
                extra=data.get("extra", {}),
                filter=data.get("filter"),
                output=None if output is None else cls.Output.from_dict(output),
                requires=frozenset(file.normalize_path(req) for req in data.get("requires", [])),
                allow_fail=data.get("allow_fail"),
                run_once=data.get("run_once", False),
            )

        def get_command(
            self,
            file_path: str | Path | None = None,
            out_dir: str | Path | None = ".",
            extra_vars: dict[str, str] = {},
            extra_args: str | None = None,
        ) -> str | None:
            """Generates the command to run the tool on a file, with all variables substituted.
            Returns `None` if the tool is disabled.

            In addition to other variables, the following variables are available:
            - `$FILE`: The full path to the file.
            - `$OUTDIR`: The output directory.
            - `$PARENT`: The parent directory of the file.
            - `$ENTRYPATH`: The file/dir entry path in the original filesytem.
            - `$FILENAME`: The name of the file (without its parent path).
            - `$USERNAME`: The username part of the file path, if applicable
                           (eg. `\\Users\\foo\\NTUSER.dat` or `/home/foo/.profile`).
            """
            config = self.file.file_list.config
            if out_dir is None:
                out_dir = Path(".")
            elif isinstance(out_dir, str):
                out_dir = Path(out_dir)
            if file_path is None:
                file_path = out_dir / self.file.path
            elif isinstance(file_path, str):
                file_path = Path(file_path)
            var_dict = config.dir_vars() | extra_vars
            var_dict |= {
                "FILE": str(file_path),
                "OUTDIR": str(out_dir),
                "PARENT": str(file_path.parent),
            }
            if "ENTRYPATH" not in var_dict:
                if file_path.is_relative_to(out_dir):
                    var_dict["ENTRYPATH"] = str(file_path.relative_to(out_dir))
                else:
                    var_dict["ENTRYPATH"] = str(file_path)
            if "FILENAME" not in var_dict:
                var_dict["FILENAME"] = file_path.name
            cmd: str | None
            if self.name is not None:
                tool = config.get_tool(self.name)
                if not tool.enabled:
                    LOGGER.info(f"Tool '{tool.name}' is disabled in config, skipping...")
                    return None
                cmd = tool.cmd
                if tool.args:
                    cmd += f" {tool.args}"
                for name, value in self.extra.items():
                    arg = tool.args_extra.get(name)
                    if arg is None:
                        raise KeyError(f"Extra argument '{name}' not found in tool '{self.name}'")
                    cmd += f" {arg}"
                    var_dict[name] = str(value)
            else:
                cmd = self.cmd
            if cmd is None:
                raise ValueError("Tool must have either 'name' or 'cmd' key")
            if extra_args is not None:
                cmd += f" {extra_args}"
            return sub_vars(cmd, var_dict)

        def run(
            self,
            file_path: str | Path | None = None,
            out_dir: str | Path | None = ".",
            entry_path: str | PurePath | None = None,
            extra_vars: dict[str, str] = {},
            extra_args: str | None = None,
            silent: bool = False,
        ) -> int | None:
            """Runs the tool on a file, with all variables substituted. Returns the return code,
            or `None` if the tool did not run (disabled, has already run and `run_once` is set,
            or the file does not match the filter).

            In addition to other variables, the following variables are available:
            - `$FILE`: The full path to the file.
            - `$OUTDIR`: The output directory.
            - `$PARENT`: The parent directory of the file.
            - `$ENTRYPATH`: The file/dir entry path in the original filesytem.
            - `$FILENAME`: The name of the file (without its parent path).
            - `$USERNAME`: The username part of the file path, if applicable
                           (eg. `\\Users\\foo\\NTUSER.dat` or `/home/foo/.profile`).
            """
            if entry_path is not None:
                if isinstance(entry_path, str):
                    entry_path = PurePath(entry_path)
                if self.filter is not None and not entry_path.match(self.filter):
                    LOGGER.info(
                        f"Skipping tool for file '{entry_path}' (filter mismatch: {self.filter})"
                    )
                    return None
                extra_vars = extra_vars | {
                    "ENTRYPATH": str(entry_path),
                    "FILENAME": entry_path.name,
                }
                if (username := get_username(entry_path)) is not None:
                    extra_vars["USERNAME"] = username
            if out_dir is None:
                out_dir = Path(".")
            elif isinstance(out_dir, str):
                out_dir = Path(out_dir)
            if file_path is None:
                file_path = out_dir / self.file.path
            elif isinstance(file_path, str):
                file_path = Path(file_path)

            if (cmd := self.get_command(file_path, out_dir, extra_vars, extra_args)) is None:
                return None

            if self.run_once:
                if self.has_run:
                    LOGGER.info("Tool already ran once, skipping...")
                    return None
                self._has_run.set()
            config = self.file.file_list.config
            if self.name is None or self.allow_fail is not None:
                check = not self.allow_fail
            else:
                check = not config.get_tool(self.name).allow_fail

            LOGGER.info(f"Running command: {cmd}")
            if self.output is not None:
                var_dict = config.dir_vars() | extra_vars
                var_dict |= {
                    "FILE": str(file_path),
                    "OUTDIR": str(out_dir),
                    "PARENT": str(file_path.parent),
                }
                out_path = Path(sub_vars(self.output.path, var_dict))
                LOGGER.debug(
                    f"Writing output to file: '{out_path}' (%s, %s STDERR)",
                    "appending" if self.output.append else "overwriting",
                    "with" if self.output.stderr else "no",
                )
                out_parent = out_path.parent
                if not out_parent.exists():
                    LOGGER.debug(f"Creating directory: {out_parent}")
                    out_parent.mkdir(parents=True)
                with open(out_path, "a" if self.output.append else "w") as out_file:
                    proc_res = subprocess.run(
                        cmd,
                        shell=True,
                        check=check,
                        stdout=out_file,
                        stderr=subprocess.STDOUT if self.output.stderr else None,
                    )
                    if self.output.append:
                        out_file.write("\n")
            elif silent:
                LOGGER.debug("Silent mode: command STDOUT will be suppressed")
                proc_res = subprocess.run(cmd, shell=True, check=check, stdout=subprocess.DEVNULL)
            else:
                proc_res = subprocess.run(cmd, shell=True, check=check)
            if (ret := proc_res.returncode) == 0:
                LOGGER.info("Command succeeded")
            else:
                LOGGER.warning(f"Command failed (returned {ret})")
            return ret

        @property
        def has_run(self) -> bool:
            """Returns whether the tool has already run."""
            return bool(self._has_run)

        def __str__(self) -> str:
            if self.name:
                s = f"Tool: '{self.name}'"
            else:
                s = f"Command: '{self.cmd}'"
            s += f" [path: '{self.file.path}']"
            return s

        def __hash__(self) -> int:
            return hash(
                (
                    self.name,
                    self.cmd,
                    tuple(self.extra.items()),
                    self.requires,
                    self.output,
                    self.file,
                    self.allow_fail,
                    self.run_once,
                )
            )

    @dataclass(frozen=True)
    class File:
        """File or directory to extract or list, with optional tools to run on it.
        Acts as a container for a list of `Tool` instances."""

        path: str
        file_list: FileList = field(repr=False)
        tools: list[FileList.Tool] = field(default_factory=list)
        overwrite: bool = True

        @classmethod
        def from_str(cls, data: str, file_list: FileList, overwrite: bool = True) -> Self:
            """Creates a simple `File` instance from a string path."""
            return cls(path=cls.normalize_path(data), file_list=file_list, overwrite=overwrite)

        @classmethod
        def from_dict(cls, data: FileList.YamlFilesFile | str | Any, file_list: FileList) -> Self:
            """Creates a `File` instance from a dict or string. If a string is provided,
            it is assumed to be a path to the file, and no tools are added."""
            if isinstance(data, str):
                return cls.from_str(data, file_list)
            if not (isinstance(data, dict) and "path" in data):
                raise KeyError("Missing 'path' key")
            file = cls.from_str(data["path"], file_list, data.get("overwrite", True))
            if "tool" in data:
                if isinstance(data["tool"], dict):
                    file.tools.append(FileList.Tool.from_dict(data["tool"], file))
                else:
                    raise TypeError("Invalid 'tool' key (must be a dict)")
            if "tools" in data:
                if isinstance(data["tools"], list):
                    file.tools.extend(FileList.Tool.from_dict(tool, file) for tool in data["tools"])
                else:
                    raise TypeError("Invalid 'tools' key (must be a list)")
            return file

        @classmethod
        def from_file_or_str(cls, file: Self | str, file_list: FileList) -> Self:
            """Creates a `File` instance from a string path, or a `File` instance (no-op)."""
            if isinstance(file, str):
                return cls.from_str(file, file_list)
            return file

        @staticmethod
        def normalize_path(path: str) -> str:
            """Normalizes a path by replacing backslashes with forward slashes
            and removing the `C:` drive letter."""
            return path.replace("\\", "/").lstrip("C:/").lstrip("c:/").strip("/")

        def __hash__(self) -> int:
            return hash((self.path, tuple(self.tools), self.file_list.config))

    def __post_init__(self) -> None:
        self.sort_files()

    @classmethod
    def from_dict(cls, data: YamlFiles | Any, config: Config) -> Self:
        """Creates a `FileList` instance from a dict with a list of files to extract,
        and optionally tools to run on them."""
        if not (isinstance(data, dict) and "files" in data):
            raise KeyError("Missing 'files' key")
        if not isinstance(files := data["files"], list):
            raise TypeError("'files' must be a list")
        file_list = cls(files=[], config=config)
        file_list.extend(FileList.File.from_dict(file, file_list) for file in files)
        return file_list

    @classmethod
    def from_yaml_file(cls, yaml_file: str | Path, config: Config) -> Self:
        """Parses a YAML file and return a list of files/directories to extract,
        and optionally tools to run on them."""
        try:
            with open(yaml_file, "r") as file:
                data: FileList.YamlFiles | Any = yaml.safe_load(file)
        except FileNotFoundError:
            print_error(f"File '{yaml_file}' not found", exit_code=1)
        return cls.from_dict(data, config)

    @classmethod
    def empty(cls, config: Config) -> Self:
        """Creates an empty `FileList` instance with the given configuration."""
        return cls(files=[], config=config)

    def sort_files(self) -> None:
        """Sorts files by dependencies using a topological sort algorithm."""
        sorter: TopologicalSorter[str] = TopologicalSorter()
        for file in self.files:
            sorter.add(file.path)
            for tool in file.tools:
                for req in tool.requires:
                    if req not in self:
                        raise ValueError(f"{tool} requires unknown file '{req}'")
                sorter.add(file.path, *tool.requires)
        sorted_files = list(sorter.static_order())
        indices = {path: i for i, path in enumerate(sorted_files)}
        self.files.sort(key=lambda file: indices[file.path])

    def reset_tools(self) -> None:
        """Resets the `has_run` flag for all tools."""
        LOGGER.debug("Resetting tools 'has_run' status...")
        for file in self.files:
            for tool in file.tools:
                tool._has_run.reset()

    def append(self, file: File | str) -> None:
        """Appends a `File` or file path to the list."""
        self.files.append(FileList.File.from_file_or_str(file, self))
        self.sort_files()

    def extend(self, files: Iterable[File | str]) -> None:
        """Extends the list with a list of `File`s or file paths."""
        self.files.extend(FileList.File.from_file_or_str(file, self) for file in files)
        self.sort_files()

    def __bool__(self) -> bool:
        return bool(self.files)

    def __add__(self, other: FileList) -> FileList:
        """Merges two `FileList` instances."""
        if not isinstance(other, FileList):
            raise NotImplementedError(
                f"Cannot merge {type(self).__name__} with {type(other).__name__}"
            )
        if self.config != other.config:
            raise ValueError(f"Cannot merge {type(self).__name__}s with different configurations")
        return FileList(files=self.files + other.files, config=self.config)

    def __iter__(self) -> Iterator[File]:
        return iter(self.files)

    def __contains__(self, item: str | File) -> bool:
        if isinstance(item, str):
            return any(file.path == item for file in self.files)
        return item in self.files

    @overload
    def __getitem__(self, item: int) -> File: ...
    @overload
    def __getitem__(self, item: slice) -> Self: ...

    def __getitem__(self, item: int | slice) -> File | Self:
        if isinstance(res := self.files[item], list):
            return self.__class__(files=res, config=self.config)
        return res

    def __len__(self) -> int:
        return len(self.files)
