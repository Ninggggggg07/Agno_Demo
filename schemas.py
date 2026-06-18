from typing import List

from pydantic import BaseModel, Field


class EngagementReport(BaseModel):
    score: int = Field(..., description="Engagement score from 1 (boring) to 10 (highly engaging)")
    boring_sections: List[str] = Field(
        ..., description="Specific sections or topics in the content that feel dull, dense, or hard to follow"
    )
    suggestions: List[str] = Field(
        ..., description="Concrete suggestions to make the content more engaging (examples, stories, interactivity, etc.)"
    )
