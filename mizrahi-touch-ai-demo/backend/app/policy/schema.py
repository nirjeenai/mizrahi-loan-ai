"""The loan-completion configuration contract. A published version of this schema is the single source of truth for
document requirements, follow-up policy, Talk settings and message templates; nothing below is read from code
constants. Field bounds are the bank's envelope: a value outside them cannot be saved, whatever the editor wants."""
from __future__ import annotations

import re
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# The last six families have no review rubric: an upload is stored for the banker's review, never marked valid by AI.
Family = Literal["id_document", "payslip", "bank_statement", "purpose_proof", "tax_form", "business_registration",
                 "pnl_statement", "company_registry", "signatory_authority", "financial_statements",
                 "business_bank_statement"]
Entity = Literal["individual", "company"]
Day = Literal["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
Channel = Literal["in_app", "message", "voice"]
PROMPT_VARIABLES = ("first_name", "missing_documents", "secure_upload_link", "next_step")
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Condition(_Strict):
    """All given keys must hold. `employment` matches when ANY of the applicant's income sources is listed, so a salaried
    and self-employed applicant gets both sets once; `registration` is the applicant's VAT registration."""
    employment: Optional[list[Literal["salaried", "self_employed", "allowance"]]] = None
    registration: Optional[list[Literal["vat_exempt", "vat_registered"]]] = None
    entity: Optional[list[Entity]] = None
    purposes: Optional[list[str]] = None


class RequirementRules(_Strict):
    months: Optional[int] = Field(None, ge=1, le=6)
    coverage_days: Optional[int] = Field(None, ge=30, le=180)
    max_age_days: Optional[int] = Field(None, ge=7, le=365)
    joint_satisfies_all: Optional[bool] = None
    check_expiry: Optional[bool] = None
    min_tax_year_offset: Optional[int] = Field(None, ge=1, le=3)


class DocumentRequirement(_Strict):
    id: str = Field(..., pattern=r"^[A-Z][A-Z_]{2,40}$")
    family: Family
    per: Literal["applicant", "account", "case"]
    required: bool = True
    label_he: str = Field(..., min_length=2, max_length=80)
    hint_he: str = Field("", max_length=300)
    why_he: str = Field("", max_length=300)
    alternatives_he: list[str] = Field(default_factory=list, max_length=6)
    condition: Optional[Condition] = None
    rules: RequirementRules = RequirementRules()

    @field_validator("alternatives_he")
    @classmethod
    def _alternatives(cls, v: list[str]) -> list[str]:
        if any(not 2 <= len(x) <= 120 for x in v):
            raise ValueError("מסמך חלופי חייב להכיל 2–120 תווים")
        return v


class Purpose(_Strict):
    label_he: str = Field(..., max_length=60)
    proof_he: str = Field(..., max_length=120)
    entity: Entity = "individual"


class Product(_Strict):
    label_he: str = Field(..., max_length=60)
    purposes: dict[str, Purpose]


class Scope(_Strict):
    environment: Literal["demo", "staging", "prod"]
    product: str


class Validation(_Strict):
    low_confidence_threshold: float = Field(0.6, ge=0.3, le=0.95)
    undetermined_route: Literal["HUMAN_REVIEW"] = "HUMAN_REVIEW"


class CallWindow(_Strict):
    timezone: Literal["Asia/Jerusalem"] = "Asia/Jerusalem"
    days: list[Day]
    from_: str = Field(..., alias="from")
    to: str

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_validator(mode="after")
    def _window(self) -> "CallWindow":
        for v in (self.from_, self.to):
            if not _HHMM.match(v):
                raise ValueError(f"שעה לא תקינה: {v}")
        if not ("08:00" <= self.from_ < self.to <= "20:00"):
            raise ValueError("חלון הפנייה חייב להיות בתוך 08:00–20:00 (מעטפת הבנק) ושעת הסיום אחרי שעת ההתחלה")
        if not self.days:
            raise ValueError("לא הוגדרו ימי פנייה")
        if "SAT" in self.days:
            raise ValueError("אין פנייה בשבת (מעטפת הבנק)")
        return self


class Followup(_Strict):
    auto_followup_enabled: bool = True
    presence_ttl_seconds: int = Field(90, ge=20, le=600)
    in_app_idle_nudge_minutes: int = Field(5, ge=1, le=120)
    abandonment_grace_minutes: int = Field(20, ge=1, le=1440)
    unknown_presence_extra_minutes: int = Field(10, ge=0, le=240)
    channel_order: list[Channel] = ["in_app", "voice"]
    min_hours_between_calls: int = Field(24, ge=4, le=168)
    max_attempts_per_case: int = Field(2, ge=1, le=3)
    max_attempts_per_case_per_day: int = Field(1, ge=1, le=3)
    max_attempts_per_customer_per_day: int = Field(2, ge=1, le=5)
    call_window: CallWindow
    holidays: list[str] = []
    on_exhausted_attempts: Literal["HUMAN_REVIEW"] = "HUMAN_REVIEW"
    statement_extends_grace_minutes: int = Field(30, ge=0, le=240)

    @field_validator("holidays")
    @classmethod
    def _dates(cls, v: list[str]) -> list[str]:
        for d in v:
            date.fromisoformat(d)
        return sorted(set(v))

    @model_validator(mode="after")
    def _order(self) -> "Followup":
        if not self.channel_order or self.channel_order[0] != "in_app":
            raise ValueError("סדר הערוצים חייב להתחיל בתיקון עצמי בפורטל (in_app)")
        if len(set(self.channel_order)) != len(self.channel_order):
            raise ValueError("ערוץ מופיע פעמיים בסדר הערוצים")
        if self.max_attempts_per_case_per_day > self.max_attempts_per_case:
            raise ValueError("מכסה יומית גדולה ממכסת התיק")
        return self


class Talk(_Strict):
    mode: Literal["off", "simulation", "live"] = "simulation"
    enabled: bool = True
    link_ttl_minutes: int = Field(1440, ge=15, le=10080)
    reconcile_after_minutes: int = Field(10, ge=1, le=120)
    max_provider_errors: int = Field(2, ge=0, le=5)


class Templates(_Strict):
    in_app_correction: str = Field(..., max_length=600)
    link_message: str = Field(..., max_length=600)
    reminder: str = Field(..., max_length=600)
    completed: str = Field(..., max_length=600)


class LoanPolicy(_Strict):
    schema_version: Literal["1.0"]
    scope: Scope
    product: Product
    document_requirements: list[DocumentRequirement]
    validation: Validation = Validation()
    customer_messages: dict[str, str] = {}
    followup: Followup
    talk: Talk = Talk()
    templates: Templates

    @model_validator(mode="after")
    def _unique(self) -> "LoanPolicy":
        ids = [r.id for r in self.document_requirements]
        if len(ids) != len(set(ids)):
            raise ValueError("מזהה דרישה מופיע פעמיים")
        if not any(r.required for r in self.document_requirements):
            raise ValueError("לא הוגדרה אף דרישת חובה")
        if self.scope.environment != "demo" and self.talk.mode == "simulation":
            raise ValueError("מצב סימולציה מותר רק בסביבת DEMO")
        for name, text in {**self.templates.model_dump(), **self.customer_messages}.items():
            for var in re.findall(r"{{\s*(\w+)\s*}}", text):
                if var not in PROMPT_VARIABLES:
                    raise ValueError(f"משתנה לא מוכר בתבנית {name}: {var}")
        return self


class TalkPrompt(_Strict):
    schema_version: Literal["1.0"] = "1.0"
    locale: Literal["he-IL"] = "he-IL"
    opening_locked: str = Field(..., max_length=400)
    instructions: str = Field(..., min_length=10, max_length=4000)
    allowed_variables: list[str] = list(PROMPT_VARIABLES)

    @model_validator(mode="after")
    def _vars(self) -> "TalkPrompt":
        unknown = [v for v in self.allowed_variables if v not in PROMPT_VARIABLES]
        if unknown:
            raise ValueError("משתנים לא מורשים: " + ", ".join(unknown))
        for var in re.findall(r"{{\s*(\w+)\s*}}", self.instructions):
            if var not in self.allowed_variables:
                raise ValueError(f"משתנה לא מוכר בהנחיות: {var}")
        return self


KINDS = {"loan_policy": LoanPolicy, "talk_prompt": TalkPrompt}


def parse(kind: str, config: dict) -> BaseModel:
    return KINDS[kind].model_validate(config)
