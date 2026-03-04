import re

THEMES = {
    "intern_student": [
        "intern", "internship", "trainee", "graduate", "student", "thesis", "master thesis",
        "summer job", "sommarjobb", "praktik", "examensarbete", "sommarjobb"
    ],
    "tech": [
        "software", "developer", "engineer", "backend", "frontend", "full stack", "fullstack",
        "devops", "sre", "cloud", "platform", "security", "cyber", "embedded", "systems",
        "python", "java", "c++", "c#", "javascript", "node", "sql", "utvecklare", "mjukvaruingenjör", "systemutvecklare"
    ],
    "data_ai": [
        "data", "analytics", "analyst", "machine learning", "ml", "ai", "deep learning",
        "pytorch", "tensorflow", "nlp", "llm", "computer vision", "mlops", "bigquery", "dataanalytiker", "analytiker"
    ],
    "physics_engineering": [
        "physics", "engineering", "simulation", "modeling", "modelling", "optimization",
        "energy", "battery", "solar", "signal processing", "control", "robotics"
    ],
    "economy": [
        "economy", "economics", "business", "finance", "quant", "valuation",
        "operations research", "supply chain", "industrial", "management", "strategy",
        "business analyst", "product analyst"
    ],
}

NEGATIVE_JOB_SIGNALS = [
    # Helps avoid labeling generic marketing as job candidate
    "discount", "sale", "offer", "buy now", "limited time", "promo", "promotion"
]

def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text

def theme_hits(text: str):
    text = normalize(text)
    hits = []
    for theme, kws in THEMES.items():
        for kw in kws:
            if kw in text:
                hits.append((theme, kw))
                break
    return hits

def is_job_candidate(subject: str, body: str, sender: str = "") -> tuple[bool, int, list[tuple[str, str]]]:
    """
    Returns: (candidate_bool, score, hits)
    score is a rough confidence score based on number of themes matched.
    """
    text = normalize(subject + "\n" + body + "\n" + sender)

    hits = theme_hits(text)

    # guardrail: avoid obvious marketing-only emails
    if not hits and any(neg in text for neg in NEGATIVE_JOB_SIGNALS):
        return (False, 0, [])

    # Broad rule: any theme hit => candidate
    score = min(100, 30 * len(hits))  # 1 theme=30, 2=60, 3+=90/100
    return (len(hits) > 0, score, hits)