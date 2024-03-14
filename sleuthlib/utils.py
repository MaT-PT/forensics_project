SIZE_UNITS = ["B", "K", "M", "G", "T", "P"]


def pretty_size(size: int, compact: bool = True) -> str:
    if compact:
        units = SIZE_UNITS
    else:
        units = [f" {unit}{'B' if unit != 'B' else ''}" for unit in SIZE_UNITS]

    for unit in units:
        if size < 1024:
            break
        size //= 1024
    return f"{size}{unit}"
