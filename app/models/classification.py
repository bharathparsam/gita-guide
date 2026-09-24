from pydantic import BaseModel


class ClassificationResult(BaseModel):
    in_scope: bool
    primary_situation: str
    primary_emotion: str
    root_conflict: str