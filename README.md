# Gita Guide

Gita Guide is an early-stage Python application that classifies a user's personal
situation before providing reflective guidance inspired by the Bhagavad Gita.

The current version accepts a message through a command-line interface and uses
[JEV](https://openrouter.ai/typesafe/jev-1.13) through OpenRouter's Decisions API
to identify:

- Whether the message is in scope for reflective life guidance
- The primary life situation
- The primary emotion
- The underlying inner conflict

The guidance and verse-recommendation layer has not been implemented yet.

## Requirements

- Python 3.10 or newer
- An [OpenRouter](https://openrouter.ai/) API key with access to JEV

## Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the dependencies:

```bash
python -m pip install -r requirements.txt
```

Create a `.env` file in the project root:

```dotenv
OPENROUTER_API_KEY=your_openrouter_api_key
```

The `.env` file is ignored by Git and should not be committed.

## Run the application

From the project root, run:

```bash
python -m app.main
```

Enter a personal situation when prompted:

```text
Tell me what you're going through: I worked hard but failed my interview and now I feel useless.
```

The application returns a structured classification similar to:

```json
{
  "in_scope": true,
  "primary_situation": "fear_of_failure",
  "primary_emotion": "sadness",
  "root_conflict": "attachment_to_results"
}
```

JEV is probabilistic, so classifications can vary between requests.

## How it works

```text
User message
    |
    v
Command-line interface (app/main.py)
    |
    v
Classification service
    |
    v
JEV classifier -> OpenRouter Decisions API
    |
    v
ClassificationResult
```

JEV receives the message and four typed questions in one request. It uses a
`noul` question for the in-scope decision and `choice` questions for situation,
emotion, and root conflict. Returned choices are validated against the local
taxonomy before a `ClassificationResult` is created.

## Project structure

```text
app/
├── classifiers/
│   ├── jev_classifier.py       # OpenRouter request and response validation
│   └── taxonomy.py             # Supported classification labels
├── models/
│   └── classification.py       # Structured result model
├── services/
│   └── classification_service.py
├── config.py                   # Environment configuration
└── main.py                     # CLI entry point
evals/
└── classification_cases.json  # Placeholder for labeled evaluation cases
tests/
├── test_classifier.py          # Placeholder for automated classifier tests
└── test_jev.py                 # Live JEV integration script
```

## Classification taxonomy

The supported labels are defined in `app/classifiers/taxonomy.py`.

Situation examples include fear of failure, outcome anxiety, comparison, anger,
grief, confusion, lack of motivation, purpose, discipline, and relationship
conflict.

Emotion examples include fear, sadness, anger, envy, guilt, confusion,
frustration, hopelessness, and calm.

Root-conflict examples include attachment to results, fear, comparison, ego,
desire, duty conflict, lack of self-control, loss, and uncertainty.

Each dimension also includes an `other` category.

## Live JEV check

To call JEV directly with the sample payload in the integration script, run:

```bash
python tests/test_jev.py
```

This script makes a real, billable OpenRouter API request. It is currently a
manual integration check rather than an isolated automated test.

## Current status

Implemented:

- Interactive CLI input
- OpenRouter/JEV classification
- Response-shape and taxonomy validation
- Basic handling for empty input, network errors, and invalid API responses

Planned:

- Automated classifier tests with mocked API responses
- Labeled evaluation cases and accuracy measurement
- Bhagavad Gita verse and teaching retrieval
- Guidance generation based on the classification
