from typing import Literal, Optional
from pydantic import BaseModel, Field


class CitedItem(BaseModel):
    text: str = Field(description="Simplified, plain-English statement or document name.")
    citation: str = Field(description="Exact source clause code, e.g., 'C1', 'C4'.")


class DeadlineItem(BaseModel):
    event: str = Field(description="What the deadline or date is for.")
    date: str = Field(description="Exact date/time string as stated in the notice.")
    citation: str = Field(description="Exact source clause code, e.g., 'C2'.")


class HardEligibilityRules(BaseModel):
    target_branches: list[str] = Field(
        default=["ALL"],
        description="Allowed branches (e.g. ['CS', 'IT', 'AIML']) or ['ALL'] if open to all.",
    )
    target_years: list[str] = Field(
        default=["ALL"],
        description="Allowed years (e.g. ['FE', 'SE', 'TE', 'BE']) or ['ALL'].",
    )
    target_categories: list[str] = Field(
        default=["ALL"],
        description="Allowed caste/reservation categories (e.g. ['OBC', 'SC', 'ST', 'EBC']) or ['ALL'].",
    )
    min_cgpa: Optional[float] = Field(default=None, description="Minimum required CGPA if specified.")
    max_income: Optional[int] = Field(default=None, description="Maximum annual family income in INR if specified.")
    max_backlogs: Optional[int] = Field(default=None, description="Maximum allowed active backlogs if specified.")
    citation: Optional[str] = Field(default=None, description="Primary clause code stating these criteria.")


class CanonicalNotice(BaseModel):
    title: str = Field(description="Clear, concise title of the notice.")
    category: Literal["Scholarship", "Exam", "Event", "Fee", "General"]
    urgency: Literal["High", "Medium", "Low"]
    summary_bullets: list[CitedItem] = Field(
        description="3 to 5 plain-English action points summarizing the notice."
    )
    deadlines: list[DeadlineItem] = Field(default_factory=list)
    required_documents: list[CitedItem] = Field(default_factory=list)
    hard_rules: HardEligibilityRules
    edge_conditions: list[CitedItem] = Field(
        default_factory=list,
        description="Nuanced or conditional rules (e.g., 'Not applicable to hostelites') with exact C# citation.",
    )