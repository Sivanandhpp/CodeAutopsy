"""Analysis schemas for engine outputs."""

from __future__ import annotations

from pydantic import BaseModel
from pydantic import ConfigDict


class AnalysisFinding(BaseModel):
    rule_id: str
    engine_source: str
    file_path: str
    line_number: int
    severity: str
    defect_family: str
    message: str
    fix_hint: str | None = None
    cwe_id: str | None = None
    owasp_ref: str | None = None
    code_snippet: str | None = None
    issue_type: str | None = None
    end_line: int | None = None
    column: int | None = None

    model_config = ConfigDict(from_attributes=True, extra="ignore")
