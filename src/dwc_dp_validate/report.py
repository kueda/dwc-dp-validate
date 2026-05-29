"""Validation report types: Severity, Issue, and Report."""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import click


class Severity(str, Enum):
    """Validation issue severity level."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


_SEVERITY_ORDER = {Severity.INFO: 0, Severity.WARNING: 1, Severity.ERROR: 2}


@dataclass
class Issue:
    """A single validation finding."""

    severity: Severity
    message: str
    resource: Optional[str] = None
    row: Optional[int] = None
    field_name: Optional[str] = None


@dataclass
class Report:
    """Aggregates validation Issues across all check layers."""

    issues: list[Issue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        """True when no ERROR-level issues are present."""
        return not any(i.severity == Severity.ERROR for i in self.issues)

    def add(self, issue: Issue) -> None:
        """Append an issue to the report."""
        self.issues.append(issue)

    def filtered(self, min_level: str = "warning") -> list[Issue]:
        """Return issues at or above min_level severity."""
        threshold = _SEVERITY_ORDER[Severity(min_level)]
        return [i for i in self.issues if _SEVERITY_ORDER[i.severity] >= threshold]

    def _header(self, shown: list["Issue"], min_level: str, color: bool) -> str:
        status = "VALID" if self.valid else "INVALID"
        if color and self.valid:
            status = click.style(status, fg="green")
        elif color:
            status = click.style(status, fg="red")
        if not shown:
            return f"{status} — no issues at or above '{min_level}'"
        return f"{status} — {self._severity_summary(shown, color=color)}"

    @staticmethod
    def _sev_label(sev: "Severity", color: bool) -> str:
        label = sev.value.upper()
        if color:
            if sev == Severity.ERROR:
                return click.style(label, fg="red")
            if sev == Severity.WARNING:
                return click.style(label, fg="yellow")
        return label

    @staticmethod
    def _severity_summary(issues: list["Issue"], color: bool = False) -> str:
        counts: dict[Severity, int] = {}
        for issue in issues:
            counts[issue.severity] = counts.get(issue.severity, 0) + 1
        parts = []
        for sev in (Severity.ERROR, Severity.WARNING, Severity.INFO):
            n = counts.get(sev, 0)
            if n:
                noun = sev.value + ("s" if n != 1 else "")
                part = f"{n} {noun}"
                if color:
                    if sev == Severity.ERROR:
                        part = click.style(part, fg="red")
                    elif sev == Severity.WARNING:
                        part = click.style(part, fg="yellow")
                parts.append(part)
        return ", ".join(parts)

    def as_text(self, min_level: str = "warning", color: bool = False) -> str:
        """Format issues as a human-readable string."""
        shown = self.filtered(min_level)
        header = self._header(shown, min_level, color)
        if not shown:
            return header
        lines = [header]
        for issue in shown:
            loc = ""
            if issue.resource:
                loc = f" [{issue.resource}"
                if issue.row is not None:
                    loc += f" row {issue.row}"
                if issue.field_name:
                    loc += f" field '{issue.field_name}'"
                loc += "]"
            lines.append(f"{self._sev_label(issue.severity, color)}{loc}: {issue.message}")
        return "\n".join(lines)

    def as_text_summary(self, min_level: str = "warning", color: bool = False) -> str:
        """Format issues as human-readable text, collapsing repeated row-level issues."""
        shown = self.filtered(min_level)
        header = self._header(shown, min_level, color)
        if not shown:
            return header

        solo: list[Issue] = []
        groups: dict[tuple, list[Issue]] = defaultdict(list)
        for issue in shown:
            if issue.row is not None:
                key = (issue.severity, issue.resource, issue.field_name, issue.message)
                groups[key].append(issue)
            else:
                solo.append(issue)

        lines = [header, ""]

        for issue in solo:
            loc = ""
            if issue.resource:
                loc = f" [{issue.resource}"
                if issue.field_name:
                    loc += f" field '{issue.field_name}'"
                loc += "]"
            lines.append(f"{self._sev_label(issue.severity, color)}{loc}: {issue.message}")

        for (severity, resource, field_name, message), group in groups.items():
            count = len(group)
            loc = ""
            if resource:
                loc = f" [{resource}"
                if field_name:
                    loc += f" field '{field_name}'"
                loc += "]"
            noun = "row" if count == 1 else "rows"
            lines.append(
                f"{self._sev_label(severity, color)}{loc} ({count} {noun}): {message}"
            )

        return "\n".join(lines)

    def as_json(self, min_level: str = "warning") -> str:
        """Format issues as a JSON string."""
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
