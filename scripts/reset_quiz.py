"""
reset_quiz.py - Wipe all student quiz data (keeps schema and questions intact).
Reads DB credentials from .env — no hardcoded passwords.

Usage:
    python scripts/reset_quiz.py --confirm
"""
import argparse
import os
from pathlib import Path

# Load .env manually (no dependency on dotenv package)
def load_env():
    env_path = Path(__file__).parent.parent / ".env"
    env = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env

def parse_db_url(url: str):
    """Parse postgresql+asyncpg://user:pass@host:port/db"""
    url = url.replace("postgresql+asyncpg://", "").replace("postgresql://", "")
    user_pass, host_db = url.split("@", 1)
    user, password = user_pass.split(":", 1)
    host_port, dbname = host_db.rsplit("/", 1)
    if ":" in host_port:
        host, port = host_port.split(":", 1)
    else:
        host, port = host_port, "5432"
    return user, password, host, port, dbname

def reset(confirm: bool):
    if not confirm:
        print("Dry run — pass --confirm to actually reset the DB.")
        return

    env = load_env()
    db_url = env.get("DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not db_url:
        print("[ERROR] DATABASE_URL not found in .env")
        return

    try:
        import asyncpg
        import asyncio

        user, password, host, port, dbname = parse_db_url(db_url)

        async def run():
            conn = await asyncpg.connect(
                user=user, password=password,
                host=host, port=int(port), database=dbname
            )
            await conn.execute(
                "TRUNCATE TABLE studentanswers, session, students RESTART IDENTITY CASCADE;"
            )
            await conn.close()
            print("[OK] Successfully cleared all student data.")

        asyncio.run(run())
    except Exception as e:
        print(f"[ERROR] Failed to reset DB: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset quiz sessions and student data.")
    parser.add_argument("--confirm", action="store_true", help="Confirm reset")
    args = parser.parse_args()
    reset(args.confirm)
