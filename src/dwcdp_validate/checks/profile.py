"""Layer 2: DwC-DP profile/metadata conformance checks."""
from __future__ import annotations

from ..report import Issue, Report, Severity

KNOWN_DWC_DP_PROFILES = {
    "https://raw.githubusercontent.com/gbif/dwc-dp/0.1/dwc-dp/dwc-dp-profile.json",
    "https://raw.githubusercontent.com/gbif/dwc-dp/master/dwc-dp/dwc-dp-profile.json",
    "http://rs.tdwg.org/dwc-dp/1.0/dwc-dp-profile.json",
}

# All table names defined in the official dwc-dp schema repository
RESERVED_RESOURCE_NAMES = {
    "agent",
    "agent-agent-role",
    "agent-identifier",
    "agent-media",
    "bibliographic-resource",
    "chronometric-age",
    "chronometric-age-agent-role",
    "chronometric-age-assertion",
    "chronometric-age-media",
    "chronometric-age-protocol",
    "chronometric-age-reference",
    "event",
    "event-agent-role",
    "event-assertion",
    "event-identifier",
    "event-media",
    "event-protocol",
    "event-provenance",
    "event-reference",
    "geological-context",
    "geological-context-media",
    "identification",
    "identification-agent-role",
    "identification-reference",
    "identification-taxon",
    "material",
    "material-agent-role",
    "material-assertion",
    "material-geological-context",
    "material-identifier",
    "material-media",
    "material-protocol",
    "material-provenance",
    "material-reference",
    "material-usage-policy",
    "media",
    "media-agent-role",
    "media-assertion",
    "media-identifier",
    "media-provenance",
    "media-usage-policy",
    "molecular-protocol",
    "molecular-protocol-agent-role",
    "molecular-protocol-assertion",
    "molecular-protocol-reference",
    "nucleotide-analysis",
    "nucleotide-analysis-assertion",
    "nucleotide-sequence",
    "occurrence",
    "occurrence-agent-role",
    "occurrence-assertion",
    "occurrence-identifier",
    "occurrence-media",
    "occurrence-protocol",
    "occurrence-reference",
    "organism",
    "organism-assertion",
    "organism-identifier",
    "organism-interaction",
    "organism-interaction-agent-role",
    "organism-interaction-assertion",
    "organism-interaction-media",
    "organism-interaction-reference",
    "organism-reference",
    "organism-relationship",
    "protocol",
    "protocol-reference",
    "provenance",
    "resource-relationship",
    "survey",
    "survey-agent-role",
    "survey-assertion",
    "survey-identifier",
    "survey-protocol",
    "survey-reference",
    "survey-target",
    "usage-policy",
}


def check(dp: dict, report: Report) -> None:
    """Run profile conformance checks against a parsed datapackage dict."""
    profile = dp.get("profile")
    if profile not in KNOWN_DWC_DP_PROFILES:
        report.add(Issue(
            severity=Severity.ERROR,
            message=(
                f"Top-level 'profile' is {profile!r}; "
                "expected a DwC-DP profile URL."
            ),
        ))

    for meta_field in ("id", "created", "version"):
        if not dp.get(meta_field):
            report.add(Issue(
                severity=Severity.WARNING,
                message=f"Top-level field '{meta_field}' is missing or empty.",
            ))

    for resource in dp.get("resources", []):
        name = resource.get("name", "<unnamed>")

        if resource.get("profile") != "tabular-data-resource":
            report.add(Issue(
                severity=Severity.ERROR,
                resource=name,
                message="Resource 'profile' must be 'tabular-data-resource'.",
            ))

        mediatype = resource.get("mediatype", "")
        if mediatype not in ("text/csv", "text/tab-separated-values"):
            report.add(Issue(
                severity=Severity.WARNING,
                resource=name,
                message=(
                    f"Resource 'mediatype' is {mediatype!r}; "
                    "expected 'text/csv' or 'text/tab-separated-values'."
                ),
            ))

        if name not in RESERVED_RESOURCE_NAMES:
            report.add(Issue(
                severity=Severity.WARNING,
                resource=name,
                message=(
                    f"Resource name {name!r} is not in the DwC-DP reserved name list."
                ),
            ))
