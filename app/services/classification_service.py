from app.classifiers.jev_classifier import classify_with_jev
from app.models.classification import ClassificationResult


def classify(message: str) -> ClassificationResult:
    return classify_with_jev(message)
