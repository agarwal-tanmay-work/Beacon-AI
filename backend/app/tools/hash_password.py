"""Create an ADMIN_PASSWORD_HASH for the admin portal.

    python -m app.tools.hash_password

Prompts for the password (nothing is echoed or stored) and prints a hash to put in the
ADMIN_PASSWORD_HASH environment variable. Works without any other configuration.
"""

import getpass
import os
import sys

# Importing app.core.security pulls in app.core.config, which insists on a SECRET_KEY / DATABASE_URL even though
# hashing needs neither - provide throw-away values so this tool runs on a bare checkout.
os.environ.setdefault("SECRET_KEY", "hash-tool-" + "x" * 32)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from app.core.security import hash_secret  # noqa: E402


def main() -> int:
    password = getpass.getpass("New admin password: ")
    if len(password) < 12:
        print("Please use at least 12 characters (a few random words work well).", file=sys.stderr)
        return 1
    if getpass.getpass("Repeat password: ") != password:
        print("The passwords do not match.", file=sys.stderr)
        return 1
    print("\nSet this as ADMIN_PASSWORD_HASH (keep the quotes out of your hosting dashboard's value field):\n")
    print(hash_secret(password))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
