"""Safely encode the Supabase DB password in the local .env file."""

from getpass import getpass
from pathlib import Path
import re
from urllib.parse import quote


ENV_FILE = Path(__file__).with_name(".env")
POOLER_HOST_START = re.compile(r"@(?=aws-[A-Za-z0-9-]+\.pooler\.supabase\.com)")
USER_PREFIX = re.compile(r"^(postgres(?:ql)?://[^:]+):")


def main():
    if not ENV_FILE.is_file():
        raise SystemExit("web/backend/.env was not found.")

    lines = ENV_FILE.read_text(encoding="utf-8").splitlines(keepends=True)
    index = next(
        (i for i, line in enumerate(lines) if line.lstrip().startswith("DATABASE_URL=")),
        None,
    )
    if index is None:
        raise SystemExit("DATABASE_URL= was not found in web/backend/.env.")

    line = lines[index]
    ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
    value = line.split("=", 1)[1].strip()
    marker = POOLER_HOST_START.search(value)
    if not marker:
        raise SystemExit(
            "Could not recognize the Supabase Session pooler URL. "
            "Copy its URI into DATABASE_URL first, including the [YOUR-PASSWORD] placeholder."
        )

    before_host = value[:marker.start()]
    prefix = USER_PREFIX.match(before_host)
    if not prefix:
        raise SystemExit("The DATABASE_URL format was not recognized; .env was not changed.")

    password = getpass("Enter the Supabase database password (input is hidden): ")
    if not password:
        raise SystemExit("No password entered; .env was not changed.")

    updated = f"{prefix.group(1)}:{quote(password, safe='')}@{value[marker.start() + 1:]}"
    lines[index] = f"DATABASE_URL={updated}{ending}"
    ENV_FILE.write_text("".join(lines), encoding="utf-8")
    print("Updated DATABASE_URL in web/backend/.env. Password was not printed.")


if __name__ == "__main__":
    main()
