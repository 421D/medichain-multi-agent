"""Evaluation test cases with ground truth for automated scoring."""

EVALUATION_CASES = [
    {
        "case_id": "EVAL-001",
        "name": "emergency_meningitis",
        "initial_message": (
            "I have a terrible headache and high fever for 2 days. "
            "My neck is very stiff and I can't look down. "
            "I also noticed a rash on my legs that doesn't go away when I press on it."
        ),
        "follow_up_answers": [
            "The headache is at the back of my head, constant and throbbing, about 9 out of 10.",
            "The fever is around 39.5 degrees. No medications. 25 years old, male.",
            "My roommate was sick last week. I feel confused and sleepy.",
        ],
        "ground_truth": {
            "primary_diagnosis": "Bacterial meningitis",
            "expected_in_ddx": ["Bacterial meningitis", "Viral meningitis", "Subarachnoid hemorrhage"],
            "expected_safety_flag": "red",
            "expected_tests": ["Lumbar puncture", "Blood cultures", "CT head"],
            "expected_cdss": ["qsofa"],
        },
    },
    {
        "case_id": "EVAL-002",
        "name": "common_uti",
        "initial_message": (
            "I have burning when I urinate for 3 days. "
            "I need to go much more frequently and there is a strong smell."
        ),
        "follow_up_answers": [
            "Burning at the end of urination. Started gradually.",
            "No blood, no fever, no back pain. 32 female, sexually active.",
            "No vaginal discharge. Had one UTI 2 years ago.",
        ],
        "ground_truth": {
            "primary_diagnosis": "Urinary tract infection",
            "expected_in_ddx": ["Urinary tract infection", "Cystitis"],
            "expected_safety_flag": "green",
            "expected_tests": ["Urinalysis", "Urine culture"],
            "expected_cdss": [],
        },
    },
    {
        "case_id": "EVAL-003",
        "name": "chest_pain_acs",
        "initial_message": (
            "I am a 55 year old male with diabetes and hypertension. "
            "Crushing chest pain for 2 hours radiating to left arm and jaw. "
            "Pain 8/10, short of breath, sweating heavily. "
            "Taking metformin and lisinopril. Father had MI at 52."
        ),
        "follow_up_answers": [
            "Pain started suddenly while resting. Nothing makes it better.",
            "No aspirin taken. Never had chest pain like this before.",
        ],
        "ground_truth": {
            "primary_diagnosis": "Acute myocardial infarction",
            "expected_in_ddx": ["Acute myocardial infarction", "Unstable angina", "Aortic dissection"],
            "expected_safety_flag": "red",
            "expected_tests": ["ECG", "Troponin", "Chest X-ray"],
            "expected_cdss": ["heart_score"],
        },
    },
    {
        "case_id": "EVAL-004",
        "name": "anxiety_somatic",
        "initial_message": (
            "My heart keeps racing and I can't breathe. "
            "Happens almost every day, usually in afternoon. Tingling in my hands."
        ),
        "follow_up_answers": [
            "Started a month ago. Each episode 10-20 minutes.",
            "Very stressed at work. No chest pain, no fainting.",
            "35 male. No heart problems in family. Sleep 4-5 hours. 4 coffees daily.",
        ],
        "ground_truth": {
            "primary_diagnosis": "Panic disorder",
            "expected_in_ddx": ["Panic disorder", "Generalized anxiety disorder", "Cardiac arrhythmia"],
            "expected_safety_flag": "yellow",
            "expected_tests": ["ECG", "Thyroid function"],
            "expected_cdss": [],
        },
    },
    {
        "case_id": "EVAL-005",
        "name": "chronic_fatigue",
        "initial_message": "I just feel really tired all the time.",
        "follow_up_answers": [
            "3 months. Sleep 8 hours but wake exhausted.",
            "No weight changes. Appetite normal. Feel a bit down.",
            "28 female. Periods heavier than usual. Dizzy when standing.",
            "No thyroid history. Long office hours. Moderate stress.",
        ],
        "ground_truth": {
            "primary_diagnosis": "Iron deficiency anaemia",
            "expected_in_ddx": ["Iron deficiency anaemia", "Hypothyroidism", "Depression"],
            "expected_safety_flag": "green",
            "expected_tests": ["Full blood count", "Iron studies", "Thyroid function"],
            "expected_cdss": ["phq9"],
        },
    },
    {
        "case_id": "EVAL-006",
        "name": "child_ear_infection",
        "initial_message": (
            "My 3 year old has had fever 39C for 2 days. "
            "She pulls at her right ear and cries a lot. Won't eat."
        ),
        "follow_up_answers": [
            "Fever started 2 days ago. Had a cold last week that seemed to clear.",
            "No rash, no vomiting. Up to date on vaccinations.",
            "Goes to daycare. Several kids sick recently.",
        ],
        "ground_truth": {
            "primary_diagnosis": "Acute otitis media",
            "expected_in_ddx": ["Acute otitis media", "Upper respiratory infection"],
            "expected_safety_flag": "green",
            "expected_tests": ["Otoscopic examination"],
            "expected_cdss": [],
        },
    },
    {
        "case_id": "EVAL-007",
        "name": "pneumonia_moderate",
        "initial_message": (
            "I have had a cough with yellowish phlegm for 5 days. "
            "Fever up to 38.8. Feels hard to breathe when walking. "
            "I am 70 years old with COPD."
        ),
        "follow_up_answers": [
            "Cough started gradually. Phlegm is thick and yellow-green.",
            "Breathing rate feels fast. Feel confused sometimes. BP was 85/55 at pharmacy.",
            "Taking tiotropium for COPD. No allergies.",
        ],
        "ground_truth": {
            "primary_diagnosis": "Community-acquired pneumonia",
            "expected_in_ddx": ["Community-acquired pneumonia", "COPD exacerbation", "Lung abscess"],
            "expected_safety_flag": "red",
            "expected_tests": ["Chest X-ray", "Blood cultures", "Sputum culture"],
            "expected_cdss": ["curb65"],
        },
    },
]
