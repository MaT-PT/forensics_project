from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypedDict, get_type_hints

import yaml

from .colored_logging import print_error

if sys.version_info >= (3, 11):
    from typing import NotRequired, Self
else:
    from typing_extensions import NotRequired, Self

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Config:
    """Configuration for tools and directories, parsed from a YAML file.
    Use `Config.from_yaml_file` to parse a YAML file and return a `Config` object.
    Directories can be accessed as env vars with the prefix `DIR_` (eg. `$DIR_REGRIPPER`)."""

    tools: list[Config.Tool] = field(default_factory=list)
    directories: dict[str, str] = field(default_factory=dict)

    class YamlConfigToolCmd(TypedDict):
        """YAML dict: Command configuration for a tool, with platform-specific commands."""

        windows: NotRequired[str]
        linux: NotRequired[str]
        mac: NotRequired[str]

    class YamlConfigTool(TypedDict):
        """YAML dict: Tool configuration with name."""

        name: str
        cmd: str | Config.YamlConfigToolCmd
        args: NotRequired[str]
        args_extra: NotRequired[dict[str, str]]
        allow_fail: NotRequired[bool]
        enabled: NotRequired[bool]
        disabled: NotRequired[bool]

    class YamlConfig(TypedDict):
        """YAML dict: Top-level configuration with tools and directories."""

        tools: NotRequired[list[Config.YamlConfigTool]]
        directories: NotRequired[dict[str, str]]

    @dataclass(frozen=True)
    class ToolCmd:
        """Command configuration for a tool, with platform-specific commands.
        Use `ToolCmd.from_dict` to create a `ToolCmd` instance from a string or a dict."""

        windows: str | None = None
        linux: str | None = None
        mac: str | None = None

        @classmethod
        def from_dict(cls, data: Config.YamlConfigToolCmd | str | Any) -> Self:
            """Creates a `ToolCmd` instance from a string or a dict with platform-specific commands.
            If a string is provided, the same command is used for all platforms.
            If a dict is provided, it must have keys `windows`, `linux`, and/or `mac`."""
            if isinstance(data, str):
                return cls(windows=data, linux=data, mac=data)
            if not (isinstance(data, dict) and set() < set(data) <= set(get_type_hints(cls))):
                raise TypeError(
                    "Invalid cmd configuration (must be a string, "
                    "or a dict with keys 'windows', 'linux', and/or 'mac')"
                )
            return cls(
                windows=data.get("windows"),
                linux=data.get("linux"),
                mac=data.get("mac"),
            )

        @property
        def cmd(self) -> str:
            """Returns the command for the current platform.
            On MacOS, falls back to Linux command if `mac` is not set."""
            cmd: str | None = None
            if sys.platform == "win32":
                cmd = self.windows
            elif sys.platform == "linux":
                cmd = self.linux
            elif sys.platform == "darwin":
                cmd = self.mac or self.linux  # Fallback to Linux cmd
            assert cmd is not None, f"Could not find cmd for current platform ({sys.platform})"
            return cmd

    @dataclass(frozen=True)
    class Tool:
        """Tool configuration with name, command, optional arguments, and flags.
        Use `Tool.from_dict` to create a `Tool` instance from a dict."""

        name: str
        command: Config.ToolCmd
        args: str | None = None
        args_extra: dict[str, str] = field(default_factory=dict)
        allow_fail: bool | None = None
        enabled: bool = True

        @classmethod
        def from_dict(cls, data: Config.YamlConfigTool | Any) -> Self:
            """Creates a `Tool` instance from a dict with name, command,
            optional arguments, and flags."""
            if not (isinstance(data, dict) and "name" in data and "cmd" in data):
                raise KeyError("Missing 'name' or 'cmd' key")
            name = data["name"]
            enabled = data.get("enabled")
            disabled = data.get("disabled")
            if enabled is not None:
                if disabled is not None and bool(enabled) == bool(disabled):
                    raise ValueError(
                        f"Tool '{name}': Incoherent values for 'enabled' and 'disabled'"
                    )
                enabled = bool(enabled)
            elif disabled is not None:
                enabled = not disabled
            else:
                enabled = True
            return cls(
                name=name,
                command=Config.ToolCmd.from_dict(data["cmd"]),
                args=data.get("args"),
                args_extra=data.get("args_extra", {}),
                allow_fail=data.get("allow_fail"),
                enabled=enabled,
            )

        @property
        def cmd(self) -> str:
            """Returns the command for the current platform."""
            return self.command.cmd

        def __hash__(self) -> int:
            return hash(
                (
                    self.name,
                    self.command,
                    self.args,
                    frozenset(self.args_extra.items()),
                    self.allow_fail,
                    self.enabled,
                )
            )

    @classmethod
    def from_dict(cls, data: Config.YamlConfig | Any) -> Self:
        """Creates a list of `Tool`s and directories from a dict."""
        return cls(
            tools=[Config.Tool.from_dict(tool) for tool in data.get("tools", [])],
            directories=data.get("directories", {}),
        )

    @classmethod
    def from_yaml_file(cls, yaml_file_path: str | Path) -> Self:
        """Parses a YAML file and creates a list of `Tool`s and directories."""
        try:
            with open(yaml_file_path, "r") as file:
                data: Config.YamlConfig | Any = yaml.safe_load(file)
        except FileNotFoundError:
            print_error(f"Config file '{yaml_file_path}' not found", exit_code=1)
        return cls.from_dict(data)

    def get_tool(self, name: str) -> Tool:
        """Returns a tool by name, or raises a KeyError if not found."""
        try:
            tool = next(tool for tool in self.tools if tool.name == name)
            return tool
        except StopIteration:
            raise KeyError(f"Tool '{name}' not found in config") from None

    def dir_vars(self) -> dict[str, str]:
        """Returns a dict with directories as environment variables (with prefix `DIR_`)."""
        return {f"DIR_{key.upper()}": value for key, value in self.directories.items()}

    def __hash__(self) -> int:
        return hash((frozenset(self.tools), frozenset(self.directories.items())))
