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
    tools: list[Config.Tool] = field(default_factory=list)
    directories: dict[str, str] = field(default_factory=dict)

    class YamlConfigToolCmd(TypedDict):
        windows: NotRequired[str]
        linux: NotRequired[str]
        mac: NotRequired[str]

    class YamlConfigTool(TypedDict):
        name: str
        cmd: str | Config.YamlConfigToolCmd
        args: NotRequired[str]
        args_extra: NotRequired[dict[str, str]]
        allow_fail: NotRequired[bool]
        enabled: NotRequired[bool]
        disabled: NotRequired[bool]

    class YamlConfig(TypedDict):
        tools: NotRequired[list[Config.YamlConfigTool]]
        directories: NotRequired[dict[str, str]]

    @dataclass(frozen=True)
    class ToolCmd:
        windows: str | None = None
        linux: str | None = None
        mac: str | None = None

        @classmethod
        def from_dict(cls, data: Config.YamlConfigToolCmd | str | Any) -> Self:
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
        name: str
        command: Config.ToolCmd
        args: str | None = None
        args_extra: dict[str, str] = field(default_factory=dict)
        allow_fail: bool | None = None
        enabled: bool = True

        @classmethod
        def from_dict(cls, data: Config.YamlConfigTool | Any) -> Self:
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
        return cls(
            tools=[Config.Tool.from_dict(tool) for tool in data.get("tools", [])],
            directories=data.get("directories", {}),
        )

    @classmethod
    def from_yaml_file(cls, yaml_file: str | Path) -> Self:
        """Parse a YAML file and return a list of tools and directories"""
        try:
            with open(yaml_file, "r") as file:
                data: Config.YamlConfig | Any = yaml.safe_load(file)
        except FileNotFoundError:
            print_error(f"Config file '{yaml_file}' not found", exit_code=1)
        return cls.from_dict(data)

    def get_tool(self, name: str) -> Tool:
        try:
            tool = next(tool for tool in self.tools if tool.name == name)
            return tool
        except StopIteration:
            raise KeyError(f"Tool '{name}' not found in config") from None

    def dir_vars(self) -> dict[str, str]:
        return {f"DIR_{key.upper()}": value for key, value in self.directories.items()}

    def __hash__(self) -> int:
        return hash((frozenset(self.tools), frozenset(self.directories.items())))
