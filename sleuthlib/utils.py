import shutil

SIZE_UNITS = ["B", "K", "M", "G", "T", "P"]
REQUIRED_TOOLS = ["mmls", "fls", "icat"]


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


def check_program_in_path(name: str, path: str | None = None) -> bool:
    res = shutil.which(name, path=path)
    return res is not None


def check_required_tools(path: str | None = None) -> None:
    for tool in REQUIRED_TOOLS:
        if not check_program_in_path(tool, path):
            raise FileNotFoundError(f"{tool} not found in {'PATH' if path is None else path}")
