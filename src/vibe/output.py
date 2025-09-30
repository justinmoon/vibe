from __future__ import annotations

import sys

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
NC = "\033[0m"


def success(message: str, *args: object) -> None:
    print(GREEN + (message % args if args else message) + NC)


def warning(message: str, *args: object) -> None:
    print(YELLOW + (message % args if args else message) + NC, file=sys.stderr)


def error(message: str, *args: object) -> None:
    print(RED + (message % args if args else message) + NC, file=sys.stderr)


def error_exit(message: str, *args: object, exit_code: int = 1) -> None:
    error(message, *args)
    sys.exit(exit_code)


def info(message: str, *args: object) -> None:
    print(message % args if args else message)
