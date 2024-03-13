from argparse import Action, ArgumentParser, ArgumentTypeError, Namespace
from typing import Any, Callable, Literal, Mapping, Sequence, TypeVar

_T = TypeVar("_T")


def int_min(min_val: int = 0) -> Callable[[str], int]:
    def int_min_inner(value: str) -> int:
        try:
            n = int(value)
        except ValueError as e:
            raise ArgumentTypeError(str(e))
        if n < min_val:
            raise ArgumentTypeError(f"should be an integer >= {min_val}")
        return n

    return int_min_inner


class ListableAction(Action):
    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str,
        nargs: int | Literal["?", "*", "+"] | None = None,
        default: _T | None = None,
        type: Callable[[str], _T] | None = None,
        choices: Mapping[str, str] | None = None,
        required: bool = False,
        help: str | None = None,
        metavar: str | tuple[str, ...] | None = None,
    ) -> None:
        if choices is None or not isinstance(choices, Mapping):
            raise ValueError("choices must be a mapping of option names -> descriptions")
        super(ListableAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=nargs,
            default=default,
            type=type,
            choices=set(choices.keys()) | {"list"},
            required=required,
            help=help,
            metavar=metavar,
        )
        self._choices_map = choices

    def __call__(
        self,
        parser: ArgumentParser,
        namespace: Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        setattr(namespace, self.dest, values)
        if values is None:
            values = []
        elif isinstance(values, str):
            values = [values]
        if "list" in values:
            print(f"Supported choices for {self.metavar or self.dest}:")
            for k, v in self._choices_map.items():
                print(f"  {k}: {v}")
            parser.exit()
