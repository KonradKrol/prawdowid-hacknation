from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

Label = Literal["confirmed", "false", "misleading", "insufficient_evidence", "not_verifiable"]
Status = Literal["ok", "needs_clarification", "out_of_scope", "invalid_input", "rate_limited", "technical_error"]
Stance = Literal["supports", "refutes", "context"]
Level = Literal["strong", "moderate", "weak", "none"]
Notice = Literal["archival_material", "instructions_ignored", "partial_check", "known_narrative", "source_status"]
Channel = Literal["web", "api", "adapter"]


class CheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(validation_alias=AliasChoices("text", "question"))
    lang: Literal["pl"] = "pl"
    clarifies: str | None = Field(default=None, max_length=100)


class Evidence(BaseModel):
    source_id: str
    stance: Stance
    field: Literal["excerpt", "published_on"]
    quote: str | None
    title: str
    publisher: str
    url: str
    published_on: str | None
    retrieved_on: str
    source_type: str
    is_primary: bool
    archival: bool


class Premise(BaseModel):
    code: str
    text: str
    effect: Literal["plus", "minus", "neutral"]


class Strength(BaseModel):
    level: Level = "none"
    premises: list[Premise] = Field(default_factory=list)


class ContextMismatch(BaseModel):
    field: Literal["date", "place", "person", "number", "scope", "source"]
    claim_value: str
    source_value: str
    explanation: str


class Item(BaseModel):
    id: str
    claim: str
    claim_span: str | None = None
    kind: Literal["verdict", "answer"]
    label: Label | None = None
    answer: str | None = None
    reason: str
    strength: Strength = Field(default_factory=Strength)
    context_mismatch: ContextMismatch | None = None
    missing_evidence: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)


class NoticeItem(BaseModel):
    type: Notice
    text: str


class InputInfo(BaseModel):
    text_masked: str
    kind: Literal["text", "url", "text_with_url"] = "text"
    url: str | None = None
    masked: list[str] = Field(default_factory=list)


class Meta(BaseModel):
    corpus_version: str
    corpus_documents: int
    model: str | None
    prompt_version: str
    elapsed_ms: int
    estimated_cost_usd: float | None = None
    cached: bool = False


class CheckResult(BaseModel):
    contract_version: Literal["1.0"] = "1.0"
    id: str
    created_at: str
    channel: Channel
    lang: Literal["pl"] = "pl"
    status: Status
    parent_id: str | None = None
    message: str | None = None
    clarification_question: str | None = None
    summary: str | None = None
    input: InputInfo
    items: list[Item] = Field(default_factory=list)
    notices: list[NoticeItem] = Field(default_factory=list)
    meta: Meta


class PublicSource(BaseModel):
    id: str
    title: str
    publisher: str
    url: str
    domain: str
    type: str
    published_on: str | None = None
    checked_on: str
    usage: str | None = None


class SourcesResponse(BaseModel):
    documents: int
    domains: int
    source_types: list[str]
    version: str
    sources: list[PublicSource]
