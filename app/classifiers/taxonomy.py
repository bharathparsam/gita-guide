TAXONOMY_VERSION = "2.1"


# Fine-grained application themes grounded in concerns or qualities discussed in the
# Bhagavad Gita. This is deliberately a separate dimension: the catalog mixes lived
# situations, emotions, behavioral patterns, inner conflicts, and aspirational
# qualities, so flattening it into one of the broader taxonomies below would make
# those existing fields semantically inconsistent.
GITA_TRAITS = {
    "anxiety": "General unease or apprehension without one clearly named feared event.",
    "fear": "Fear of danger, harm, judgment, or another threatening consequence.",
    "worry": "Repeated concern about something that may happen or go wrong.",
    "grief": "Sorrow connected to bereavement, separation, or an irreversible ending.",
    "sadness": "Feeling unhappy, emotionally low, hurt, or disappointed.",
    "distress": "Acute emotional strain that is not more precisely captured by another trait.",
    "moroseness": "Persistent gloom, sullenness, or withdrawal into a dark mood.",
    "overthinking": "Repetitive analysis or rumination that prevents rest or action.",
    "restless_mind": "A mind that repeatedly wanders and is difficult to settle.",
    "distraction": "Attention being repeatedly pulled away from the intended focus.",
    "confusion": "Difficulty understanding the situation or knowing what is right.",
    "doubt": "Uncertainty about whether a belief, choice, or course of action is sound.",
    "indecision": "Inability to choose between identifiable alternatives.",
    "self_doubt": "Lack of confidence in one's own ability, worth, or judgment.",
    "anger": "Anger, rage, or a strong impulse to react against someone or something.",
    "frustration": "Irritation caused by being blocked, delayed, or unable to make progress.",
    "lust": "Sexual craving that dominates attention or conduct.",
    "greed": "A drive to acquire or keep more wealth, power, or resources.",
    "attachment": "Difficulty releasing dependence on a person, object, role, or outcome.",
    "obsession": "A person, object, or idea occupying attention in an overpowering way.",
    "temptation": "A pull toward an action that conflicts with the person's considered intention.",
    "addictive_desire": "A recurring craving reinforced despite the person's wish to stop.",
    "fear_of_failure": "Avoidance or distress centered specifically on the possibility of failing.",
    "failure": "Responding to a setback or an outcome already experienced as failure.",
    "success": "Questions about handling, defining, or responding to achieved success.",
    "result_obsession": "Preoccupation with obtaining a particular result rather than present effort.",
    "performance_pressure": "Stress about meeting expectations or performing to a required standard.",
    "procrastination": "Delaying a known task despite intending or needing to begin it.",
    "career_comparison": "Comparing career progress, title, pay, or recognition with other people.",
    "purpose": "Questions about meaning, calling, values, or the direction of one's life.",
    "motivation": "Difficulty finding or sustaining the drive to act.",
    "discipline": "Building or maintaining consistent action aligned with an intention.",
    "laziness": "Avoiding effort mainly because effort feels undesirable.",
    "oversleeping": "Sleeping excessively or allowing sleep to interfere with responsibilities.",
    "poor_routine": "An inconsistent daily pattern that undermines intended responsibilities.",
    "lack_of_self_control": "Repeated inability to regulate senses, habits, or impulses.",
    "impulsiveness": "Acting quickly on an urge without sufficient reflection.",
    "extreme_behaviour": "A pattern of excess or deprivation rather than moderation.",
    "jealousy": "Fear or resentment about losing a valued relationship or position to another.",
    "envy": "Pain at another person's advantage together with wanting what they have.",
    "hatred": "Sustained hostility or aversion toward a person or group.",
    "resentment": "Lingering anger about a perceived wrong, insult, or unfairness.",
    "forgiveness": "A wish or struggle to release resentment after being wronged.",
    "conflict": "An interpersonal disagreement, clash, or unresolved dispute.",
    "insult": "Responding to humiliation, disrespect, or an attack on dignity.",
    "criticism": "Giving, receiving, or dwelling on negative evaluation.",
    "need_for_approval": "Dependence on others' acceptance or favorable judgment.",
    "harsh_speech": "Speech that is cruel, hostile, needlessly injurious, or uncontrolled.",
    "compassion": "Concern for suffering together with a wish to respond with care.",
    "pride": "Elevated self-regard tied to achievements, qualities, or status.",
    "arrogance": "Assuming superiority and treating others as lesser.",
    "ego": "Attachment to identity, being right, status, or a threatened self-image.",
    "need_for_recognition": "Seeking praise, visibility, credit, or acknowledgment.",
    "show_off": "Displaying ability, possessions, or virtue primarily to impress others.",
    "humility": "A wish to act without superiority, self-display, or inflated self-importance.",
    "calmness": "Seeking or maintaining freedom from agitation in the present moment.",
    "equanimity": "Steadiness across favorable and unfavorable outcomes or experiences.",
    "contentment": "Enoughness or peace without continually seeking more.",
    "patience": "Capacity to wait or persist without reacting prematurely.",
    "tolerance": "Bearing discomfort, difference, or provocation without retaliation.",
    "courage": "Acting despite fear when the action is considered worthwhile.",
    "fearlessness": "Freedom from fear as a quality being sought or expressed.",
    "determination": "Firm resolve to continue a chosen course.",
    "fortitude": "Endurance and steadiness through sustained difficulty or pain.",
    "serenity": "Deep mental quiet and composure rather than momentary relief.",
    "truthfulness": "Concern with honesty, deception, or speaking what is true.",
    "gentleness": "Responding without harshness in manner, action, or speech.",
    "nonviolence": "Avoiding harm in action, speech, or intention.",
    "money_obsession": "Persistent preoccupation with earning, possessing, or accumulating money.",
    "covetousness": "Wanting to possess what belongs to another person.",
    "fear_of_loss": "Fear centered on losing a person, possession, position, or security.",
    "material_comparison": "Comparing possessions, lifestyle, or material status with others.",
    "loss": "Responding to something valued that has already been lost.",
    "unexpected_change": "Difficulty adapting to an unplanned change in circumstances.",
    "pain": "Physical or emotional suffering that is central to the message.",
    "rejection": "Responding to being refused, excluded, left, or not chosen.",
    "uncertainty": "Difficulty living with an unknown future or incomplete information.",
    "feeling_stuck": "A sense of being unable to move forward despite wanting change.",
}


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
        "A broad question about meaning, identity, calling, values, direction in life, or the "
        "qualities of an ideal, virtuous, spiritually mature, or 'perfect' person rather "
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
