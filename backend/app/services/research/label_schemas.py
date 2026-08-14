from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Confidence = Literal["HIGH", "MEDIUM", "LOW"]
LabelStatus = Literal["OK", "UNREADABLE", "PARTIAL", "UNSUPPORTED", "ERROR", "NO_IMAGE"]


class LabeledText(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=500)
    language: str = Field(min_length=1, max_length=20, default="unknown")


class UncertainLabelText(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=200)


class FiberComposition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fiber_original: str = Field(min_length=1, max_length=200)
    fiber_normalized: str = Field(min_length=0, max_length=100, default="")
    percentage: int | None = Field(default=None, ge=0, le=100)
    confidence: Confidence


class LabeledField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str = Field(min_length=1, max_length=300)
    confidence: Confidence


class LlmWashLabelAttributes(BaseModel):
    model_config = ConfigDict(extra="forbid")
    readable: bool
    raw_visible_text: list[LabeledText] = Field(default_factory=list, max_length=50)
    composition: list[FiberComposition] = Field(default_factory=list, max_length=15)
    size: LabeledField = Field(default_factory=lambda: LabeledField(value="UNKNOWN", confidence="LOW"))
    country_of_origin: LabeledField = Field(default_factory=lambda: LabeledField(value="UNKNOWN", confidence="LOW"))
    brand: LabeledField = Field(default_factory=lambda: LabeledField(value="UNKNOWN", confidence="LOW"))
    style_code: LabeledField = Field(default_factory=lambda: LabeledField(value="UNKNOWN", confidence="LOW"))
    care_instructions: list[str] = Field(default_factory=list, max_length=20)
    care_symbols_detected: list[str] = Field(default_factory=list, max_length=20)
    uncertain_text: list[UncertainLabelText] = Field(default_factory=list, max_length=20)
    unknown_fields: list[str] = Field(default_factory=list, max_length=30)
    warnings: list[str] = Field(default_factory=list, max_length=20)


class WashLabelEvidence(LlmWashLabelAttributes):
    evidence_id: str
    image_id: str
    image_type: Literal["WASH_LABEL"]
    product_code: str
    sheet: str
    anchor_row: int
    anchor_column: int
    image_sha256: str
    mime_type: Literal["image/jpeg", "image/png"]
    width: int
    height: int
    bytes: int
    original_width: int
    original_height: int
    original_bytes: int
    preprocessing_version: str
    request_size_bytes: int
    model: str
    prompt_version: str
    latency_ms: int = 0
    cache_status: Literal["HIT", "MISS"]
    llm_used: bool
    status: LabelStatus = "OK"
    composition_sum: int | None = None
    composition_sum_valid: bool | None = None


class LlmHangtagAttributes(BaseModel):
    model_config = ConfigDict(extra="forbid")
    readable: bool
    raw_visible_text: list[LabeledText] = Field(default_factory=list, max_length=50)
    brand: LabeledField = Field(default_factory=lambda: LabeledField(value="UNKNOWN", confidence="LOW"))
    style_code: LabeledField = Field(default_factory=lambda: LabeledField(value="UNKNOWN", confidence="LOW"))
    model: LabeledField = Field(default_factory=lambda: LabeledField(value="UNKNOWN", confidence="LOW"))
    size: LabeledField = Field(default_factory=lambda: LabeledField(value="UNKNOWN", confidence="LOW"))
    declared_color: LabeledField = Field(default_factory=lambda: LabeledField(value="UNKNOWN", confidence="LOW"))
    sku: LabeledField = Field(default_factory=lambda: LabeledField(value="UNKNOWN", confidence="LOW"))
    reference: LabeledField = Field(default_factory=lambda: LabeledField(value="UNKNOWN", confidence="LOW"))
    visible_barcode_text: LabeledField = Field(default_factory=lambda: LabeledField(value="UNKNOWN", confidence="LOW"))
    composition: list[FiberComposition] = Field(default_factory=list, max_length=15)
    material: LabeledField = Field(default_factory=lambda: LabeledField(value="UNKNOWN", confidence="LOW"))
    country: LabeledField = Field(default_factory=lambda: LabeledField(value="UNKNOWN", confidence="LOW"))
    uncertain_text: list[UncertainLabelText] = Field(default_factory=list, max_length=20)
    unknown_fields: list[str] = Field(default_factory=list, max_length=30)
    warnings: list[str] = Field(default_factory=list, max_length=20)


class HangtagEvidence(LlmHangtagAttributes):
    evidence_id: str
    image_id: str
    image_type: Literal["HANGTAG"]
    product_code: str
    sheet: str
    anchor_row: int
    anchor_column: int
    image_sha256: str
    mime_type: Literal["image/jpeg", "image/png"]
    width: int
    height: int
    bytes: int
    original_width: int
    original_height: int
    original_bytes: int
    preprocessing_version: str
    request_size_bytes: int
    model_used: str
    prompt_version: str
    latency_ms: int = 0
    cache_status: Literal["HIT", "MISS"]
    llm_used: bool
    status: LabelStatus = "OK"
    composition_sum: int | None = None
    composition_sum_valid: bool | None = None
