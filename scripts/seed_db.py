"""
seed_db.py — Full database seed script.
- Inserts quiz metadata (quiz_id=1, 60 min time limit)
- Parses questions.txt and writes backend/questions.json
- Seeds the options (answer key) table in PostgreSQL

Reads credentials from .env — no hardcoded passwords.

Usage:
    python scripts/seed_db.py
"""
import re
import json
import os
import asyncio
import sys
from pathlib import Path


def load_env():
    env_path = Path(__file__).parent.parent / ".env"
    env = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def parse_db_url(url: str):
    url = url.replace("postgresql+asyncpg://", "").replace("postgresql://", "")
    user_pass, host_db = url.split("@", 1)
    user, password = user_pass.split(":", 1)
    host_port, dbname = host_db.rsplit("/", 1)
    host, port = (host_port.split(":", 1) if ":" in host_port else (host_port, "5432"))
    return user, password, host, port, dbname


def parse_questions(filename):
    with open(filename, "r", encoding="utf-8") as f:
        content = f.read()

    parts = content.split("ANSWER KEY")
    questions_text = parts[0]
    answers_text = parts[1] if len(parts) > 1 else ""

    questions = []
    question_pattern = re.compile(
        r"Question (\d+)\.\s+(.*?)\s+A\)\s+(.*?)\s+B\)\s+(.*?)\s+C\)\s+(.*?)\s+D\)\s+(.*?)(?=\nQuestion \d+\.|\Z)",
        re.DOTALL,
    )
    for match in question_pattern.finditer(questions_text):
        questions.append({
            "no": int(match.group(1)),
            "text": match.group(2).strip().replace("\n", " "),
            "options": {
                "A": match.group(3).strip().replace("\n", " "),
                "B": match.group(4).strip().replace("\n", " "),
                "C": match.group(5).strip().replace("\n", " "),
                "D": match.group(6).strip().replace("\n", " "),
            },
        })

    answers = {}
    for match in re.compile(r"Q(\d+):\s*([ABCD])").finditer(answers_text):
        answers[int(match.group(1))] = match.group(2)

    return questions, answers


async def seed(user, password, host, port, dbname, questions, answers):
    import asyncpg

    conn = await asyncpg.connect(
        user=user, password=password,
        host=host, port=int(port), database=dbname
    )
    try:
        # Upsert quiz row
        await conn.execute("""
            INSERT INTO quiz (quiz_id, name, time_limit, isactive)
            VALUES (1, 'ACE Cybersecurity Recruitments 2026', 60, true)
            ON CONFLICT (quiz_id) DO UPDATE
              SET name = EXCLUDED.name,
                  time_limit = EXCLUDED.time_limit,
                  isactive = EXCLUDED.isactive
        """)
        print("[OK] Quiz row upserted.")

        # Seed answer key
        await conn.execute("DELETE FROM options WHERE quiz_id = 1")
        await conn.executemany(
            "INSERT INTO options (quiz_id, question_no, correctanswer) VALUES (1, $1, $2)",
            [(q_no, ans) for q_no, ans in answers.items()],
        )
        print(f"[OK] Seeded {len(answers)} answers into options table.")
    finally:
        await conn.close()


def main():
    root = Path(__file__).parent.parent
    questions_file = root / "questions.txt"
    backend_dir = root / "backend"
    backend_dir.mkdir(exist_ok=True)

    # Parse questions.txt
    if not questions_file.exists():
        print(f"[ERROR] questions.txt not found at {questions_file}")
        sys.exit(1)

    questions, answers = parse_questions(str(questions_file))

    if len(questions) != 60:
        print(f"[WARN] Expected 60 questions, parsed {len(questions)}")
    if len(answers) != 60:
        print(f"[WARN] Expected 60 answers, parsed {len(answers)}")

    # Write questions.json (used by questions_loader.py at runtime)
    out_file = backend_dir / "questions.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({"quiz_id": 1, "questions": questions}, f, indent=2)
    print(f"[OK] Wrote {len(questions)} questions to {out_file}")

    # Seed DB
    env = load_env()
    db_url = env.get("DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not db_url:
        print("[ERROR] DATABASE_URL not found in .env — skipping DB seed.")
        sys.exit(1)

    user, password, host, port, dbname = parse_db_url(db_url)
    asyncio.run(seed(user, password, host, port, dbname, questions, answers))
    print("[OK] Database seeding complete.")


if __name__ == "__main__":
    main()
