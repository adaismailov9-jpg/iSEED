"""Create the local iSEED role and databases inside the Docker Postgres container.

    python scripts/create_local_db.py                 # container "postgres17"
    python scripts/create_local_db.py --container pg  # another container name

What it does (safe to run again):
  1. If backend/.env does not exist, writes it with a random password for the role "iseed".
  2. Inside the container, as the postgres superuser:
       - creates the login role "iseed" (not a superuser) and sets its password from .env
       - creates the databases "iseed" (development) and "iseed_test" (pytest), owned by "iseed"
The password is sent to psql on stdin, never on the command line.
"""
import argparse
import secrets
import subprocess
import sys
from pathlib import Path

from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BACKEND_DIR / ".env"

SQL = r"""
\set ON_ERROR_STOP on
SELECT 'CREATE ROLE iseed LOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'iseed') \gexec
ALTER ROLE iseed WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'password';
SELECT 'CREATE DATABASE iseed OWNER iseed'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'iseed') \gexec
SELECT 'CREATE DATABASE iseed_test OWNER iseed'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'iseed_test') \gexec
SELECT datname || ' ready, owner ' || pg_get_userbyid(datdba)
FROM pg_database WHERE datname IN ('iseed', 'iseed_test') ORDER BY datname;
"""


def write_env(password: str, port: int) -> None:
    ENV_FILE.write_text(
        "# Local settings. Not committed (see .gitignore). Template: .env.example\n"
        f"DATABASE_URL=postgresql+psycopg://iseed:{password}@localhost:{port}/iseed\n"
        f"TEST_DATABASE_URL=postgresql+psycopg://iseed:{password}@localhost:{port}/iseed_test\n"
        "SQL_ECHO=false\n",
        encoding="utf-8",
    )


def read_password() -> str:
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            url = make_url(line.split("=", 1)[1].strip())
            if url.username != "iseed" or not url.password:
                sys.exit("DATABASE_URL in .env must use the role 'iseed' with a password")
            return url.password
    sys.exit("DATABASE_URL not found in .env")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--container", default="postgres17")
    p.add_argument("--port", type=int, default=5432, help="host port published by the container")
    args = p.parse_args()

    if not ENV_FILE.exists():
        write_env(secrets.token_urlsafe(18), args.port)  # URL-safe: no quoting needed
        print(f"wrote {ENV_FILE} with a new random password")
    password = read_password()

    script = f"\\set password '{password}'\n" + SQL
    r = subprocess.run(
        ["docker", "exec", "-i", args.container, "psql", "-U", "postgres", "-d", "postgres", "-Atq"],
        input=script, text=True, capture_output=True,
    )
    if r.returncode != 0:
        sys.exit(f"psql failed:\n{r.stderr}")
    print(r.stdout.strip())


if __name__ == "__main__":
    main()
