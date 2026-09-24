from app.classifiers.jev_classifier import ClassificationError
from app.services.classification_service import classify


def main():
    message = input("Tell me what you're going through: ")

    try:
        result = classify(message)
    except (ClassificationError, ValueError) as exc:
        print(f"\nCould not classify your message: {exc}")
        return

    print("\nClassification:")
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
