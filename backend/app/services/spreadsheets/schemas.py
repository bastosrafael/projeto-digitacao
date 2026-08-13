from enum import StrEnum

from pydantic import BaseModel, Field


class ImageClassification(StrEnum):
    PRODUCT_IMAGE = "PRODUCT_IMAGE"
    LABEL_IMAGE = "LABEL_IMAGE"
    WASH_LABEL = "WASH_LABEL"
    HANGTAG = "HANGTAG"
    OTHER = "OTHER"


class SpreadsheetImage(BaseModel):
    image_id: str
    sheet: str
    anchor_row: int
    anchor_column: int
    width: int | None = None
    height: int | None = None
    media_reference: str
    sha256: str
    classification: ImageClassification
    related_code: str | None = None


class ProductImages(BaseModel):
    product: list[SpreadsheetImage] = Field(default_factory=list)
    labels: list[SpreadsheetImage] = Field(default_factory=list)
    wash_labels: list[SpreadsheetImage] = Field(default_factory=list)
    hangtags: list[SpreadsheetImage] = Field(default_factory=list)
    other: list[SpreadsheetImage] = Field(default_factory=list)


class ResearchPreparation(BaseModel):
    queries: list[str] = Field(default_factory=list)
    evidence_terms: dict[str, str] = Field(default_factory=dict)
    focus_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DescriptionPreparation(BaseModel):
    verified_facts: dict[str, str] = Field(default_factory=dict)
    ordered_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    policy_version: str = "duimp-v1"


class Product(BaseModel):
    product_id: str
    code: str | None = None
    code_original: str | None = None
    code_confidence: float
    sheet_name: str
    row_numbers: list[int]
    item_name: str | None = None
    ncm: str | None = None
    composition: str | None = None
    construction: str | None = None
    color: str | None = None
    size: str | None = None
    purpose: str | None = None
    dimensions: str | None = None
    weight: str | None = None
    capacity: str | None = None
    voltage: str | None = None
    power: str | None = None
    frequency: str | None = None
    battery: str | None = None
    recharge: str | None = None
    connection: str | None = None
    accessories: str | None = None
    manufacturer: str | None = None
    supplier: str | None = None
    brand: str | None = None
    packing_info: list[str] = Field(default_factory=list)
    original_values: dict[str, list[str]] = Field(default_factory=dict)
    images: ProductImages = Field(default_factory=ProductImages)
    research_preparation: ResearchPreparation = Field(default_factory=ResearchPreparation)
    description_preparation: DescriptionPreparation = Field(default_factory=DescriptionPreparation)
    status: str = "OK"
    warnings: list[str] = Field(default_factory=list)


class SheetSummary(BaseModel):
    name: str
    rows: int
    columns: int
    header_rows: list[int]
    repeated_header_rows: list[int]
    header_values: dict[str, str]
    merged_ranges: int = 0
    code_column: int | None = None
    code_header: str | None = None
    code_confidence: float = 0.0
    images_detected: int = 0
    relevant: bool = False


class AnalysisResponse(BaseModel):
    file_id: str
    main_sheet: str
    sheets: int
    rows: int
    columns: int
    header_rows: list[int]
    code_column: int | None
    code_header: str | None
    code_confidence: float
    images_detected: int
    unique_media: int
    product_images: int
    label_images: int
    wash_labels: int
    hangtags: int
    other_images: int
    codes_detected: int
    unique_products: int
    repeated_codes: dict[str, list[int]]
    auxiliary_fields: list[str]
    duration_ms: int
    warnings: list[str]
    sheet_summaries: list[SheetSummary]
    products: list[Product]
