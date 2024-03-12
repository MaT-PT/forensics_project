def pretty_size(size: int) -> str:
    for unit in ["B", "K", "M", "G", "T", "P"]:
        if size < 1024:
            return f"{size:04}{unit}"
        size //= 1024
    return f"{size:04}{unit}"
