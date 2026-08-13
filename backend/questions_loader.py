import json
import os

QUESTIONS = {}

def load_questions():
    global QUESTIONS
    filepath = os.path.join(os.path.dirname(__file__), 'questions.json')
    if not os.path.exists(filepath):
        print("Warning: questions.json not found!")
        return
        
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    # Index by question number for O(1) lookup
    for q in data.get('questions', []):
        QUESTIONS[q['no']] = q
        
    print(f"Loaded {len(QUESTIONS)} questions into memory.")

def get_question(no: int):
    return QUESTIONS.get(no)
