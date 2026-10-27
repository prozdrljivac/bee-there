"""Validate a Git commit message against the Conventional Commits header."""

import re
import sys
from pathlib import Path

HEADER_PATTERN = re.compile(r"^[a-z][a-z0-9-]*(\([^()]+\))?!?: \S.*$")


def main() -> int:
    message = Path(sys.argv[1]).read_text(encoding="utf-8")
    header = message.splitlines()[0] if message else ""
    if HEADER_PATTERN.fullmatch(header):
        return 0

    print(
        "Invalid commit message. Expected: "
        "<type>[optional scope][optional !]: <description>",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
