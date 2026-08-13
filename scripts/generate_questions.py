# generate_questions.py
# NOTE: This script is superseded by scripts/seed_db.py which handles
# both question JSON generation AND DB seeding in one step, reading
# credentials from .env rather than hardcoded values.
# Kept here for reference only.
import re
import json
import os

def parse_questions(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split into questions part and answers part
    parts = content.split('ANSWER KEY')
    questions_text = parts[0]
    answers_text = parts[1] if len(parts) > 1 else ""

    # Parse questions
    questions = []
    question_pattern = re.compile(r'Question (\d+)\.\s+(.*?)\s+A\)\s+(.*?)\s+B\)\s+(.*?)\s+C\)\s+(.*?)\s+D\)\s+(.*?)(?=\nQuestion \d+\.|\Z)', re.DOTALL)
    
    for match in question_pattern.finditer(questions_text):
        q_no = int(match.group(1))
        q_text = match.group(2).strip().replace('\n', ' ')
        opt_A = match.group(3).strip().replace('\n', ' ')
        opt_B = match.group(4).strip().replace('\n', ' ')
        opt_C = match.group(5).strip().replace('\n', ' ')
        opt_D = match.group(6).strip().replace('\n', ' ')
        
        questions.append({
            "no": q_no,
            "text": q_text,
            "options": {
                "A": opt_A,
                "B": opt_B,
                "C": opt_C,
                "D": opt_D
            }
        })
    
    # Parse answers
    answers = {}
    # Look for Q[num]: [A-D]
    answer_pattern = re.compile(r'Q(\d+):\s*([ABCD])')
    for match in answer_pattern.finditer(answers_text):
        q_no = int(match.group(1))
        ans = match.group(2)
        answers[q_no] = ans
        
    return questions, answers

def main():
    questions_file = os.path.join(os.path.dirname(__file__), '..', 'questions.txt')
    backend_dir = os.path.join(os.path.dirname(__file__), '..', 'backend')
    
    if not os.path.exists(backend_dir):
        os.makedirs(backend_dir)
        
    questions, answers = parse_questions(questions_file)
    
    if len(questions) != 60:
        print(f"Warning: Expected 60 questions, parsed {len(questions)}")
        
    if len(answers) != 60:
        print(f"Warning: Expected 60 answers, parsed {len(answers)}")

    # Write questions.json
    out_file = os.path.join(backend_dir, 'questions.json')
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump({"quiz_id": 1, "questions": questions}, f, indent=2)
    print(f"Wrote {len(questions)} questions to {out_file}")

    # DB seeding is now handled by scripts/seed_db.py
    print("questions.json written. Run 'python scripts/seed_db.py' to seed the DB.")

if __name__ == "__main__":
    main()
