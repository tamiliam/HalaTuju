
def get_quiz_questions(lang_code):
    """
    Returns the list of quiz questions based on language code.
    Defaults to English ('en') if language not found.
    """
    # English Content
    en = [
      {
        "id": "q1_modality",
        "prompt": "Which type of work sounds least tiring to you?",
        "options": [
          {"text": "Working with tools, machines, or equipment", "signals": {"hands_on": 2}},
          {"text": "Solving problems, calculations, or technical tasks", "signals": {"problem_solving": 2}},
          {"text": "Helping, teaching, or assisting people", "signals": {"people_helping": 2}},
          {"text": "Creating or designing things", "signals": {"creative": 2}},
          {"text": "Organising, coordinating, or managing tasks", "signals": {"organising": 2}}
        ]
      },
      {
        "id": "q2_environment",
        "prompt": "On most days, you’d rather be working in:",
        "options": [
          {"text": "A workshop, lab, or technical space", "signals": {"workshop": 1}},
          {"text": "An office or computer-based setting", "signals": {"office": 1}},
          {"text": "A place where you interact with many people", "signals": {"high_people": 1}},
          {"text": "Different locations (field work, site visits)", "signals": {"field": 1}},
          {"text": "No strong preference", "signals": {}}
        ]
      },
      {
        "id": "q3_learning",
        "prompt": "Which describes you better as a student?",
        "options": [
          {"text": "I learn best by doing and practising", "signals": {"hands_on": 1}},
          {"text": "I prefer understanding concepts before applying them", "signals": {"theoretical": 1}},
          {"text": "I’m okay memorising if expectations are clear", "signals": {"rote_tolerant": 1}},
          {"text": "I do better with projects than exams", "signals": {"project_based": 1}},
          {"text": "I struggle with exams under time pressure", "signals": {"exam_sensitive": 1}}
        ]
      },
      {
        "id": "q4_values",
        "prompt": "Right now, which matters more to you?",
        "options": [
          {"text": "Job stability after graduation", "signals": {"stability": 2}},
          {"text": "Income potential, even if risky", "signals": {"income_focus": 2}},
          {"text": "Opportunities to continue to a degree", "signals": {"pathway_focus": 2}},
          {"text": "Doing work that feels meaningful", "signals": {"meaning_focus": 2}},
          {"text": "Finishing studies quickly to start working", "signals": {"fast_employment": 2}}
        ]
      },
      {
        "id": "q5_energy",
        "prompt": "After a full day, what usually drains you more?",
        "options": [
          {"text": "Dealing with many people", "signals": {"low_people_tolerance": 1}},
          {"text": "Concentrating on technical or detailed work", "signals": {"mental_fatigue": 1}},
          {"text": "Physical or hands-on work", "signals": {"physical_fatigue": 1}},
          {"text": "Being under time pressure", "signals": {"time_pressure_sensitive": 1}},
          {"text": "Nothing in particular", "signals": {}}
        ]
      },
      {
        "id": "q6_survival",
        "prompt": "Which of these would make it easiest for you to continue your studies?",
        "options": [
          {"text": "Receiving a monthly allowance (pocket money)", "signals": {"allowance_priority": 3}},
          {"text": "Staying as close to my home and family as possible", "signals": {"proximity_priority": 3}},
          {"text": "Having a guaranteed job interview after I graduate", "signals": {"employment_guarantee": 2}},
          {"text": "No strong preference", "signals": {}}
        ]
      }
    ]

    # Placeholder for other languages (to be translated)
    # For now, we fallback to EN to prevent errors, but logically this allows extension.
    if lang_code == 'bm':
        return en # TODO: REPLACE WITH BM TRANSLATION
    elif lang_code == 'ta':
        return en # TODO: REPLACE WITH TAMIL TRANSLATION
    
    return en
