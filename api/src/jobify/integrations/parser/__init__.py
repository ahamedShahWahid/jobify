"""Resume parser interface + concrete implementations.

The Protocol + ParsedResume schema live in :mod:`.base`. The library/regex
implementation is in :mod:`.library`. A future LLM-backed impl will land in
:mod:`.llm` behind the same Protocol once the provider decision (spec §14 #1)
is resolved.
"""

from jobify.integrations.parser.base import (
    CertificationEntry,
    EducationEntry,
    ExperienceEntry,
    ParsedResume,
    ParserError,
    ResumeParser,
    TransientParserError,
)

__all__ = [
    "CertificationEntry",
    "EducationEntry",
    "ExperienceEntry",
    "ParsedResume",
    "ParserError",
    "ResumeParser",
    "TransientParserError",
]
