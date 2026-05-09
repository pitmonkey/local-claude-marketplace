from __future__ import annotations

from dataclasses import dataclass, field

import yaml


@dataclass
class ValidationResult:
    """Result of validating a plugin markdown file.

    Attributes:
        valid: Whether the file passed all validation checks.
        plugin_type: Detected type — ``"skill"`` or ``"subagent"``.
            Always set to a sensible default even when ``valid=False``.
        reasons: Human-readable failure reasons; non-empty only when
            ``valid=False``.
    """

    valid: bool
    plugin_type: str
    reasons: list[str] = field(default_factory=list)


def parse_frontmatter(content: str) -> dict[str, object]:
    """Extract and parse YAML frontmatter from a markdown string.

    Args:
        content: Raw markdown content that may begin with a ``---`` block.

    Returns:
        Parsed frontmatter as a dict, or an empty dict when absent or
        unparseable.
    """
    if not content.startswith("---"):
        return {}
    end = content.find("\n---", 3)
    if end == -1:
        return {}
    raw = content[3:end].strip()
    try:
        result = yaml.safe_load(raw)
        return result if isinstance(result, dict) else {}
    except yaml.YAMLError:
        return {}


def _parse_frontmatter_strict(content: str) -> tuple[dict[str, object] | None, str | None]:
    """Parse frontmatter strictly, distinguishing between absent and malformed.

    Returns:
        A 2-tuple of ``(meta, error)``.  On success ``meta`` is a dict and
        ``error`` is ``None``.  On failure ``meta`` is ``None`` and ``error``
        is a short description string.
    """
    if not content.startswith("---"):
        return None, "no YAML frontmatter"
    end = content.find("\n---", 3)
    if end == -1:
        return None, "no YAML frontmatter"
    raw = content[3:end].strip()
    try:
        result = yaml.safe_load(raw)
    except yaml.YAMLError:
        return None, "frontmatter unparseable"
    if not isinstance(result, dict):
        return None, "frontmatter unparseable"
    return result, None


def _infer_type(content: str, name_hint: str) -> str:
    """Infer plugin type from content and name heuristics.

    Args:
        content: Full markdown content (including frontmatter).
        name_hint: Filename stem or explicit name used as additional signal.

    Returns:
        ``"subagent"`` when subagent signals are present, otherwise ``"skill"``.
    """
    combined = (content + name_hint).lower()
    if "subagent" in combined or "sub-agent" in combined:
        return "subagent"
    return "skill"


def validate_plugin_file(content: str, name_hint: str = "") -> ValidationResult:
    """Validate a markdown plugin file and detect its type.

    Validation runs in order and short-circuits on the first failure:

    1. File starts with ``---`` (YAML frontmatter marker present).
    2. Frontmatter block parses as a dict.
    3. Frontmatter contains a non-empty ``name`` field.
    4. Body text after the frontmatter is longer than 50 characters.

    Type detection (only runs when all checks pass):

    1. Explicit ``type`` field in frontmatter.
    2. ``model`` or ``tools`` field present in frontmatter → ``"subagent"``.
    3. ``"subagent"`` or ``"sub-agent"`` in ``(content + name_hint).lower()``
       → ``"subagent"``.
    4. Default → ``"skill"``.

    Args:
        content: Full raw markdown content to validate.
        name_hint: Optional filename stem used as a tiebreaker for type
            detection.

    Returns:
        A :class:`ValidationResult` describing validity, detected type, and
        any failure reasons.
    """
    meta, parse_error = _parse_frontmatter_strict(content)
    if parse_error is not None:
        return ValidationResult(valid=False, plugin_type="skill", reasons=[parse_error])

    assert meta is not None  # guaranteed by the check above

    name_raw = meta.get("name")
    if not name_raw:
        return ValidationResult(valid=False, plugin_type="skill", reasons=["missing name field"])

    # Extract body — everything after the closing ---
    end = content.find("\n---", 3)
    body = content[end + 4 :].strip() if end != -1 else ""
    if len(body) <= 50:
        return ValidationResult(valid=False, plugin_type="skill", reasons=["body too short"])

    # Type detection — only reached when file is fully valid
    explicit_type = meta.get("type")
    if explicit_type:
        plugin_type = str(explicit_type)
    elif meta.get("model") or meta.get("tools"):
        plugin_type = "subagent"
    else:
        plugin_type = _infer_type(content, name_hint)

    return ValidationResult(valid=True, plugin_type=plugin_type)
