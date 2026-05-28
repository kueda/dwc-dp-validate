"""Shared test data."""

MOCK_SURVEY_SCHEMA = {
    "fields": [
        {"name": "surveyID", "constraints": {"required": True, "unique": True}},
        {"name": "eventID", "constraints": {"required": True}},
        {"name": "siteCount"},
    ]
}
