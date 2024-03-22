from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypedDict

import yaml

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
            if not (
                isinstance(data, dict) and ("windows" in data or "linux" in data or "mac" in data)
            ):
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

        def __hash__(self) -> int:
            return hash((self.windows, self.linux, self.mac))

    @dataclass(frozen=True)
    class Tool:
        name: str
        command: Config.ToolCmd
        args: str | None = None
        args_extra: dict[str, str] = field(default_factory=dict)
        enabled: bool = True

        @classmethod
        def from_dict(cls, data: Config.YamlConfigTool | Any) -> Self:
            if not (isinstance(data, dict) and "name" in data and "cmd" in data):
                raise KeyError("Missing 'name' or 'cmd' key")
            name = data["name"]
            command = Config.ToolCmd.from_dict(data["cmd"])
            args = data.get("args")
            args_extra = data.get("args_extra", {})
            enabled = data.get("enabled")
            disabled = data.get("disabled")
            if enabled is not None:
                if disabled is not None and bool(enabled) == bool(disabled):
                    raise ValueError("Incoherent values for 'enabled' and 'disabled'")
                enabled = bool(enabled)
            elif disabled is not None:
                enabled = not bool(disabled)
            else:
                enabled = True
            return cls(
                name=name, command=command, args=args, args_extra=args_extra, enabled=enabled
            )

        @property
        def cmd(self) -> str:
            return self.command.cmd

        def __hash__(self) -> int:
            return hash((self.name, self.command, self.args, tuple(self.args_extra.items())))

    @classmethod
    def from_dict(cls, data: Config.YamlConfig | Any) -> Self:
        tools = data.get("tools", [])
        directories = data.get("directories", {})
        return cls(
            tools=[Config.Tool.from_dict(tool) for tool in tools],
            directories=directories,
        )

    @classmethod
    def from_yaml_file(cls, yaml_file: str | Path) -> Self:
        """Parse a YAML file and return a list of tools and directories"""
        with open(yaml_file, "r") as file:
            data: Config.YamlConfig | Any = yaml.safe_load(file)
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
        return hash((tuple(self.tools), tuple(self.directories.items())))
