from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


_SEVERITY_ORDER = {Severity.INFO: 0, Severity.WARNING: 1, Severity.ERROR: 2}


@dataclass
class Issue:
    severity: Severity
    message: str
    resource: Optional[str] = None
    row: Optional[int] = None
    field_name: Optional[str] = None


@dataclass
class Report:
    issues: list[Issue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not any(i.severity == Severity.ERROR for i in self.issues)

    def add(self, issue: Issue) -> None:
        self.issues.append(issue)

    def filtered(self, min_level: str = "warning") -> list[Issue]:
        threshold = _SEVERITY_ORDER[Severity(min_level)]
        return [i for i in self.issues if _SEVERITY_ORDER[i.severity] >= threshold]

    def as_text(self, min_level: str = "warning") -> str:
        shown = self.filtered(min_level)
        status = "VALID" if self.valid else "INVALID"
        if not shown:
            return f"{status} — no issues at or above '{min_level}'"
        lines = [f"{status} — {len(shown)} issue(s) at or above '{min_level}'"]
        for issue in shown:
            loc = ""
            if issue.resource:
                loc = f" [{issue.resource}"
                if issue.row is not None:
                    loc += f" row {issue.row}"
                if issue.field_name:
                    loc += f" field '{issue.field_name}'"
                loc += "]"
            lines.append(f"{issue.severity.value.upper()}{loc}: {issue.message}")
        return "\n".join(lines)

    def as_json(self, min_level: str = "warning") -> str:
        shown = self.filtered(min_level)
        return json.dumps(
            {
                "valid": self.valid,
                "issues": [
                    {
                        "severity": i.severity.value,
                        "message": i.message,
                        "resource": i.resource,
                        "row": i.row,
                        "field": i.field_name,
                    }
                    for i in shown
                ],
            },
            indent=2,
        )
