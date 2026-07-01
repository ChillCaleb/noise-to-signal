from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


Tier = Literal["tier1", "tier2"]
OutputFormat = Literal["text", "html"]
Length = Literal["short", "medium", "long"]


class AnalyzeRequest(BaseModel):
    """Payload sent by the Chrome extension or another HTTP client."""

    url: Optional[str] = None
    title: Optional[str] = None
    text: Optional[str] = Field(
        default=None,
        description="Readable page text. If omitted and url is provided, the backend fetches the URL.",
    )
    tier: Tier = "tier2"
    output_format: OutputFormat = "text"
    length: Length = "medium"
    save: bool = True

    @model_validator(mode="after")
    def require_text_or_url(self) -> "AnalyzeRequest":
        if not (self.text and self.text.strip()) and not (self.url and self.url.strip()):
            raise ValueError("Provide either text or url.")
        return self


class AnalyzeResponse(BaseModel):
    id: str
    created_at: str
    title: Optional[str]
    url: Optional[str]
    summary_text: str
    analysis: Dict[str, Any]
    meta: Dict[str, Any]


class HistoryItem(BaseModel):
    id: str
    created_at: str
    title: Optional[str]
    url: Optional[str]
    summary_text: str
    tier: str
    output_format: str
    length: str


class HistoryResponse(BaseModel):
    items: List[HistoryItem]

