from typing import Any

import yaml


def parse_yaml(yaml_file: str) -> list[str]:
    """Parse a YAML file and return a list of files/directories to extract"""
    with open(yaml_file, "r") as file:
        try:
            data = yaml.safe_load(file)
        except yaml.YAMLError as exc:
            print("Error parsing YAML:", exc)
            exit(1)
    try:
        files: list[str] | Any = data["files"]
    except KeyError:
        print("Error parsing YAML: 'files' key not found")
        exit(1)
    if not isinstance(files, list):
        print("Error parsing YAML: 'files' must be a list")
        exit(1)
    return files
