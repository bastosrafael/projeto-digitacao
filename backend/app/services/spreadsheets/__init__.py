from pathlib import Path

from app.services.spreadsheets.schemas import AnalysisResponse


def analyze_workbook(path: Path, file_id: str) -> AnalysisResponse:
    # Import tardio evita ciclo quando a política DUIMP usa apenas os schemas.
    from app.services.spreadsheets.analyzer import analyze_workbook as _analyze_workbook

    return _analyze_workbook(path, file_id)

__all__ = ["analyze_workbook"]
