from __future__ import annotations

import pytest

from src.marketplace.core.validator import ValidationResult, validate_plugin_file

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LONG_BODY = "x" * 51  # just above the 50-char threshold


def _make_content(
    frontmatter: str,
    body: str = _LONG_BODY,
) -> str:
    return f"---\n{frontmatter}\n---\n{body}"


# ---------------------------------------------------------------------------
# Valid files
# ---------------------------------------------------------------------------


def test_valid_skill_returns_true_and_skill_type() -> None:
    content = _make_content("name: my-skill\ndescription: Does stuff")
    result = validate_plugin_file(content)
    assert result.valid is True
    assert result.plugin_type == "skill"
    assert result.reasons == []


def test_valid_agent_via_model_field() -> None:
    content = _make_content("name: my-agent\nmodel: claude-3-5-sonnet")
    result = validate_plugin_file(content)
    assert result.valid is True
    assert result.plugin_type == "subagent"


def test_valid_agent_via_tools_field() -> None:
    content = _make_content("name: my-agent\ntools: [bash, read]")
    result = validate_plugin_file(content)
    assert result.valid is True
    assert result.plugin_type == "subagent"


def test_valid_agent_via_explicit_type_field() -> None:
    content = _make_content("name: my-agent\ntype: subagent")
    result = validate_plugin_file(content)
    assert result.valid is True
    assert result.plugin_type == "subagent"


def test_valid_agent_via_subagent_keyword_in_body() -> None:
    body = "This subagent handles complex tasks " + "y" * 20
    content = _make_content("name: my-agent", body=body)
    result = validate_plugin_file(content)
    assert result.valid is True
    assert result.plugin_type == "subagent"


def test_valid_agent_via_subagent_keyword_in_name_hint() -> None:
    content = _make_content("name: orchestrator", body=_LONG_BODY)
    result = validate_plugin_file(content, name_hint="my-subagent-tool")
    assert result.valid is True
    assert result.plugin_type == "subagent"


def test_valid_agent_via_sub_agent_hyphenated_keyword() -> None:
    body = "This sub-agent coordinates pipelines " + "z" * 20
    content = _make_content("name: coordinator", body=body)
    result = validate_plugin_file(content)
    assert result.valid is True
    assert result.plugin_type == "subagent"


def test_explicit_type_overrides_model_field() -> None:
    """Explicit ``type`` in frontmatter wins over field-based inference."""
    content = _make_content("name: my-thing\nmodel: gpt-4\ntype: skill")
    result = validate_plugin_file(content)
    assert result.valid is True
    assert result.plugin_type == "skill"


# ---------------------------------------------------------------------------
# Invalid files
# ---------------------------------------------------------------------------


def test_invalid_no_frontmatter() -> None:
    content = "# Just markdown\n\nNo frontmatter at all."
    result = validate_plugin_file(content)
    assert result.valid is False
    assert any("frontmatter" in r for r in result.reasons)


def test_invalid_no_frontmatter_plugin_type_defaults_to_skill() -> None:
    content = "No frontmatter here."
    result = validate_plugin_file(content)
    assert result.valid is False
    assert result.plugin_type == "skill"


def test_invalid_malformed_yaml_frontmatter() -> None:
    content = "---\nname: [unclosed\n---\nBody text that is long enough to pass."
    result = validate_plugin_file(content)
    assert result.valid is False
    assert any("frontmatter" in r for r in result.reasons)


def test_invalid_frontmatter_missing_name() -> None:
    content = _make_content("description: No name here")
    result = validate_plugin_file(content)
    assert result.valid is False
    assert any("name" in r for r in result.reasons)


def test_invalid_frontmatter_empty_name() -> None:
    content = _make_content("name: \ndescription: empty name")
    result = validate_plugin_file(content)
    assert result.valid is False
    assert any("name" in r for r in result.reasons)


def test_invalid_body_too_short() -> None:
    content = "---\nname: my-skill\n---\nShort."
    result = validate_plugin_file(content)
    assert result.valid is False
    assert any("body" in r for r in result.reasons)


def test_invalid_body_exactly_50_chars_fails() -> None:
    body = "x" * 50  # exactly 50 — must fail (threshold is > 50)
    content = f"---\nname: my-skill\n---\n{body}"
    result = validate_plugin_file(content)
    assert result.valid is False


def test_invalid_body_51_chars_passes() -> None:
    body = "x" * 51
    content = f"---\nname: my-skill\n---\n{body}"
    result = validate_plugin_file(content)
    assert result.valid is True


# ---------------------------------------------------------------------------
# plugin_type is always set
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "content",
    [
        "no frontmatter at all",
        "---\nbad: [yaml\n---\nbody",
        "---\ndescription: no name\n---\n" + _LONG_BODY,
        "---\nname: ok\n---\nshort",
    ],
)
def test_plugin_type_always_set(content: str) -> None:
    result = validate_plugin_file(content)
    assert isinstance(result, ValidationResult)
    assert result.plugin_type in ("skill", "subagent")


def test_name_hint_default_empty_string() -> None:
    """Calling without name_hint should work without error."""
    content = _make_content("name: test-skill")
    result = validate_plugin_file(content)
    assert result.valid is True
