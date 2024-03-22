from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass, field
from graphlib import TopologicalSorter
from pathlib import Path
from typing import Any, Iterable, Iterator, TypedDict, overload

import yaml

from .config_parser import Config

if sys.version_info >= (3, 11):
    from typing import NotRequired, Self
else:
    from typing_extensions import NotRequired, Self

LOGGER = logging.getLogger(__name__)


def split_args(args: str) -> list[str]:
    """Split a string of arguments into a list"""
    import os
    import shlex

    return shlex.split(args, posix=os.name == "posix")


def sub_vars(s: str, var_dict: dict[str, str], upper: bool = True) -> str:
    """Substitute variables in a string"""
    for key, value in var_dict.items():
        key = key.removeprefix("$")
        s = s.replace(f"${key.upper() if upper else key}", value)
    return s


def sub_vars_all(s: str, var_dict: dict[str, str], upper: bool = True, max_iter: int = 10) -> str:
    """Substitute variables in a string, repeatedly until no more substitutions are possible"""
    for _ in range(max_iter):
        new_s = sub_vars(s, var_dict, upper)
        if new_s == s:
            return new_s
        s = new_s
    LOGGER.warning(f"Max number of iterations reached while substituting variables in: {s}")
    return s


@dataclass(frozen=True)
class FileList:
    files: list[File]
    config: Config

    class YamlFilesOutput(TypedDict):
        path: str
        append: NotRequired[bool]
        stderr: NotRequired[bool]

    class YamlFilesTool(TypedDict):
        name: NotRequired[str]
        cmd: NotRequired[str]
        extra: NotRequired[dict[str, Any]]
        output: NotRequired[str | FileList.YamlFilesOutput]
        requires: NotRequired[list[str]]

    class YamlFilesFile(TypedDict):
        path: str
        tool: NotRequired[FileList.YamlFilesTool]
        tools: NotRequired[list[FileList.YamlFilesTool]]

    class YamlFiles(TypedDict):
        files: list[str | FileList.YamlFilesFile]

    @dataclass(frozen=True)
    class Tool:
        file: FileList.File = field(repr=False)
        cmd: str | None = None
        name: str | None = None
        extra: dict[str, Any] = field(default_factory=dict)
        output: Output | None = None
        requires: frozenset[str] = field(default_factory=frozenset)

        @dataclass(frozen=True)
        class Output:
            path: str
            append: bool = False
            stderr: bool = False

            @classmethod
            def from_dict(cls, data: FileList.YamlFilesOutput | str | Any) -> Self:
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
            if isinstance(data, str):
                return cls(cmd=data, file=file)
            if not isinstance(data, dict):
                raise TypeError("Invalid tool configuration (must be a string or a dict)")
            name = data.get("name")
            cmd = data.get("cmd")
            if (name is None) == (cmd is None):
                raise ValueError("Must specify either 'name' or 'cmd' key, but not both")
            extra = data.get("extra", {})
            output_val = data.get("output")
            if output_val is None:
                output = None
            else:
                output = cls.Output.from_dict(output_val)
            requires = frozenset(data.get("requires", []))
            return cls(name=name, file=file, cmd=cmd, extra=extra, output=output, requires=requires)

        def get_command(
            self,
            file_path: str | Path | None = None,
            out_dir: str | Path | None = ".",
            extra_vars: dict[str, str] = {},
            extra_args: str | None = None,
        ) -> str | None:
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
            var_dict |= {"FILE": str(file_path), "OUTDIR": str(out_dir)}
            cmd: str | None
            if self.name is not None:
                tool = config.get_tool(self.name)
                if not tool.enabled:
                    LOGGER.info(f"Tool '{self.name}' is disabled in config")
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
                raise ValueError("Tool must have either 'cmd' or 'name' key")
            if extra_args is not None:
                cmd += f" {extra_args}"
            return sub_vars_all(cmd, var_dict)

        def run(
            self,
            file_path: str | Path | None = None,
            out_dir: str | Path | None = ".",
            extra_vars: dict[str, str] = {},
            extra_args: str | None = None,
            silent: bool = False,
            check: bool = True,
        ) -> int | None:
            cmd = self.get_command(file_path, out_dir, extra_vars, extra_args)
            if cmd is None:
                return None
            LOGGER.info(f"Running command: {cmd}")
            if self.output is not None:
                var_dict = self.file.file_list.config.dir_vars() | extra_vars
                var_dict |= {"FILE": str(file_path), "OUTDIR": str(out_dir)}
                out_path = Path(sub_vars_all(self.output.path, var_dict))
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
            ret = proc_res.returncode
            if ret == 0:
                LOGGER.info(f"Command succeeded (returned {ret})")
            else:
                LOGGER.warning(f"Command failed (returned {ret})")
            return ret

        def __str__(self) -> str:
            if self.name:
                s = f"Tool: '{self.name}'"
            else:
                s = f"Command: '{self.cmd}'"
            s += f" [file: '{self.file.path}']"
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
                )
            )

    @dataclass(frozen=True)
    class File:
        path: str
        file_list: FileList = field(repr=False)
        tools: list[FileList.Tool] = field(default_factory=list)

        @classmethod
        def from_str(cls, data: str, file_list: FileList) -> Self:
            return cls(path=cls.normalize_path(data), file_list=file_list)

        @classmethod
        def from_dict(cls, data: FileList.YamlFilesFile | str | Any, file_list: FileList) -> Self:
            if isinstance(data, str):
                return cls.from_str(data, file_list)
            if not (isinstance(data, dict) and "path" in data):
                raise KeyError("Missing 'path' key")
            res = cls.from_str(data["path"], file_list)
            if "tool" in data:
                if isinstance(data["tool"], dict):
                    res.tools.append(FileList.Tool.from_dict(data["tool"], res))
                else:
                    raise TypeError("Invalid 'tool' key (must be a dict)")
            if "tools" in data:
                if isinstance(data["tools"], list):
                    res.tools.extend(FileList.Tool.from_dict(tool, res) for tool in data["tools"])
                else:
                    raise TypeError("Invalid 'tools' key (must be a list)")
            return res

        @classmethod
        def from_file_or_str(cls, file: Self | str, file_list: FileList) -> Self:
            if isinstance(file, str):
                return cls.from_str(file, file_list)
            return file

        @staticmethod
        def normalize_path(path: str) -> str:
            return path.replace("\\", "/").lstrip("C:").lstrip("c:").strip("/")

        def __hash__(self) -> int:
            return hash((self.path, tuple(self.tools), self.file_list.config))

    def __post_init__(self) -> None:
        self.sort_files()

    @classmethod
    def from_dict(cls, data: YamlFiles | Any, config: Config) -> Self:
        if not (isinstance(data, dict) and "files" in data):
            raise KeyError("Missing 'files' key")
        files = data["files"]
        if not isinstance(files, list):
            raise TypeError("'files' must be a list")
        file_list = cls(files=[], config=config)
        file_list.extend(FileList.File.from_dict(file, file_list) for file in files)
        return file_list

    @classmethod
    def from_yaml_file(cls, yaml_file: str | Path, config: Config) -> Self:
        """Parse a YAML file and return a list of files/directories to extract"""
        with open(yaml_file, "r") as file:
            data: FileList.YamlFiles | Any = yaml.safe_load(file)
        return cls.from_dict(data, config)

    @classmethod
    def empty(cls, config: Config) -> Self:
        return cls(files=[], config=config)

    def sort_files(self) -> None:
        """Sort files by dependencies"""
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

    def append(self, file: File | str) -> None:
        """Append a File to the list"""
        self.files.append(FileList.File.from_file_or_str(file, self))
        self.sort_files()

    def extend(self, files: Iterable[File | str]) -> None:
        """Extend the list with a list of Files"""
        self.files.extend(FileList.File.from_file_or_str(file, self) for file in files)
        self.sort_files()

    def __bool__(self) -> bool:
        return bool(self.files)

    def __add__(self, other: FileList) -> FileList:
        """Merge two FileList instances"""
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
        res = self.files[item]
        if isinstance(res, list):
            return self.__class__(files=res, config=self.config)
        return res

    def __len__(self) -> int:
        return len(self.files)
