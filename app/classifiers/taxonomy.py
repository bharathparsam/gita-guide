TAXONOMY_VERSION = "1.0"


SITUATIONS = {
    "fear_of_failure": (
        "A past failure, rejection, poor performance, or fear of attempting something "
        "because failure may damage confidence or self-worth. Prefer this over grief for setbacks."
    ),
    "outcome_anxiety": (
        "Distress about a future result that is not yet known or controllable, such as an exam, "
        "interview result, promotion, health result, or plan succeeding."
    ),
    "comparison": (
        "Measuring progress, worth, possessions, or success against another person and feeling "
        "jealous, inferior, envious, or left behind."
    ),
    "anger": (
        "The central problem is rage, resentment, revenge, bitterness, or inability to forgive; "
        "use relationship_conflict when the dispute itself is primary."
    ),
    "grief": (
        "Mourning a death, separation, breakup, irreversible loss, or major ending. Do not use "
        "for an ordinary failure or disappointing result."
    ),
    "confusion": (
        "The person cannot choose between concrete actions or does not know what the right next "
        "step is; use purpose for broader questions about meaning or life direction."
    ),
    "lack_of_motivation": (
        "Low drive, apathy, procrastination, or inability to begin or continue necessary work, "
        "without a dominant impulse-control problem."
    ),
    "purpose": (
        "A broad question about meaning, identity, calling, values, or direction in life rather "
        "than a choice between specific actions. Do not use for remorse about one action or "
        "self-criticism about craving praise."
    ),
    "discipline": (
        "Repeated inability to regulate habits, cravings, impulses, attention, or distractions, "
        "including compulsive phone use or breaking commitments to oneself."
    ),
    "relationship_conflict": (
        "A disagreement, betrayal, communication breakdown, boundary problem, or tension with a "
        "partner, relative, friend, colleague, or other person."
    ),
    "other": (
        "The message is in scope but none of the supported situations clearly dominates, "
        "including moral remorse about a past action or concern about craving recognition."
    ),
}


EMOTIONS = {
    "fear": "Threat-focused fear, nervousness, worry, dread, or anxiety.",
    "sadness": "Sorrow, disappointment, hurt, loneliness, or feeling emotionally low.",
    "anger": "Anger, irritation, rage, bitterness, or resentment.",
    "envy": "Jealousy, coveting, or pain caused by another person's perceived advantage.",
    "guilt": "Remorse about one's action, regret, shame, or feeling morally at fault.",
    "confusion": "Uncertainty, indecision, mental conflict, or inability to make sense of a choice.",
    "frustration": "Feeling blocked, thwarted, impatient, or stuck despite trying.",
    "hopelessness": "Despair or belief that improvement and a way forward are impossible.",
    "calm": "No strong negative emotion is expressed; the person is reflective or emotionally steady.",
    "other": "No listed emotion clearly dominates.",
}


ROOT_CONFLICTS = {
    "attachment_to_results": (
        "Peace, identity, or self-worth depends on obtaining a particular result or reward; the "
        "person is unable to focus on right effort independently of the outcome. Select fear "
        "when anticipated harm mainly causes avoidance, and uncertainty when waiting itself is central."
    ),
    "fear": (
        "Fear of pain, rejection, failure, judgment, or harm is preventing right action. Prefer "
        "this when avoidance is central, even if an outcome also matters."
    ),
    "comparison": "Self-worth is being determined by measuring oneself against other people.",
    "ego": "Pride, status, recognition, being right, or a threatened identity dominates the conflict.",
    "desire": "A craving for pleasure, possession, attention, or a preferred experience dominates thought.",
    "duty_conflict": "Competing responsibilities or uncertainty about the ethical or rightful action.",
    "lack_of_self_control": "Impulses, habits, cravings, or distraction repeatedly override intention.",
    "loss": "The central struggle is accepting death, separation, irreversible change, or an ending.",
    "uncertainty": (
        "The future cannot be known or controlled, and waiting or not knowing is the central "
        "struggle. Prefer this over attachment_to_results when no self-worth or reward dependence is stated."
    ),
    "other": "None of the listed inner conflicts clearly applies.",
}
