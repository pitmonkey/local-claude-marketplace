"""Assert docs/deployment-contract.yaml matches the env vars the code actually reads.

The set of environment variables, their required-ness and their defaults are derived
by walking the AST of the application source (everything under ``src/``, excluding
``tests/``) looking for ``os.environ["X"]``, ``os.getenv("X", ...)`` and
``os.environ.get("X", ...)`` reads. The contract is never allowed to be a hand-written
list: this test fails both when the code grows a read with no contract entry and when
the contract carries an entry no code reads.
"""

from __future__ import annotations

import ast
import pathlib
from dataclasses import dataclass
from typing import Any

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTRACT_PATH = REPO_ROOT / "docs" / "deployment-contract.yaml"


@dataclass(frozen=True)
class EnvVar:
    """A single environment variable read, as derived from the source AST.

    ``has_default`` is True for ``os.getenv`` / ``os.environ.get`` (which never raise —
    they return ``None`` when no default is given) and False for ``os.environ[...]``
    subscripts (which raise ``KeyError``, i.e. the variable is required).

    ``default_known`` is True when the default is statically knowable — a string literal,
    or absent (meaning ``None``). It is False when the default is a non-literal expression
    (e.g. ``DB_PATH``'s ``str(data_dir / "db" / ...)``); the contract must still record a
    default, but this test cannot check its value against the code.
    """

    required: bool
    has_default: bool
    default: str | None
    default_known: bool


def _source_files() -> list[pathlib.Path]:
    """Return every .py file the deployment contract must account for."""
    files = list(REPO_ROOT.glob("*.py"))
    files.extend((REPO_ROOT / "src").rglob("*.py"))
    tests_dir = REPO_ROOT / "tests"
    return [f for f in files if tests_dir not in f.parents]


def _str_constant(node: ast.expr | None) -> str | None:
    """Return the string value of a Constant node, else None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_os_name(node: ast.expr) -> bool:
    return isinstance(node, ast.Name) and node.id == "os"


def _is_getenv_call(func: ast.expr) -> bool:
    """Match ``os.getenv(...)``."""
    return isinstance(func, ast.Attribute) and func.attr == "getenv" and _is_os_name(func.value)


def _is_environ_get_call(func: ast.expr) -> bool:
    """Match ``os.environ.get(...)``."""
    if not (isinstance(func, ast.Attribute) and func.attr == "get"):
        return False
    value = func.value
    return isinstance(value, ast.Attribute) and value.attr == "environ" and _is_os_name(value.value)


def _is_environ_subscript(node: ast.Subscript) -> bool:
    """Match ``os.environ[...]``."""
    value = node.value
    return isinstance(value, ast.Attribute) and value.attr == "environ" and _is_os_name(value.value)


class _EnvVarVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.found: dict[str, EnvVar] = {}

    def _record(self, name: str, var: EnvVar) -> None:
        existing = self.found.get(name)
        # A variable read in more than one place is recorded once; a required read
        # (subscript) always wins over an optional one.
        if existing is not None and existing.required:
            return
        self.found[name] = var

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        if (_is_getenv_call(node.func) or _is_environ_get_call(node.func)) and node.args:
            name = _str_constant(node.args[0])
            if name is not None:
                if len(node.args) < 2:
                    # No default argument -> the code default is None, statically known.
                    self._record(
                        name,
                        EnvVar(required=False, has_default=True, default=None, default_known=True),
                    )
                else:
                    literal = _str_constant(node.args[1])
                    known = isinstance(node.args[1], ast.Constant)
                    self._record(
                        name,
                        EnvVar(
                            required=False,
                            has_default=True,
                            default=literal,
                            default_known=known,
                        ),
                    )
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:  # noqa: N802
        if _is_environ_subscript(node):
            name = _str_constant(node.slice)
            if name is not None:
                self._record(
                    name,
                    EnvVar(required=True, has_default=False, default=None, default_known=True),
                )
        self.generic_visit(node)


def discover_env_vars() -> dict[str, EnvVar]:
    """AST-walk the application source and return every env var it reads."""
    visitor = _EnvVarVisitor()
    for path in _source_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        visitor.visit(tree)
    return visitor.found


def load_contract() -> dict[str, Any]:
    """Load and parse docs/deployment-contract.yaml."""
    raw: Any = yaml.safe_load(CONTRACT_PATH.read_text())
    assert isinstance(raw, dict)
    return raw


def test_contract_parses_and_kind() -> None:
    contract = load_contract()
    assert contract["kind"] == "DeploymentContract"
    assert isinstance(contract["env"], dict)
    assert isinstance(contract["resources"], dict)


def test_env_names_match_code() -> None:
    contract = load_contract()
    contract_names = set(contract["env"])
    code_names = set(discover_env_vars())

    missing_from_contract = code_names - contract_names
    stray_in_contract = contract_names - code_names

    assert not missing_from_contract and not stray_in_contract, (
        f"missing from contract (read in code, no contract entry): "
        f"{sorted(missing_from_contract)}; "
        f"stray in contract (no code reads this var): {sorted(stray_in_contract)}"
    )


def test_required_flags_are_bools_and_match_code() -> None:
    contract = load_contract()
    code_vars = discover_env_vars()
    for name, code_var in code_vars.items():
        entry = contract["env"][name]
        # A quoted 'false' would be read as required by the consumer — catch it here.
        assert isinstance(entry["required"], bool), f"{name}: required must be a real bool"
        assert entry["required"] == code_var.required, f"{name}: required flag mismatch"


def test_defaults_match_code() -> None:
    contract = load_contract()
    code_vars = discover_env_vars()
    for name, code_var in code_vars.items():
        entry = contract["env"][name]
        if not code_var.has_default:
            assert "default" not in entry, f"{name}: required var must not declare a default"
            continue
        assert "default" in entry, f"{name}: optional var must declare a default (may be null)"
        if code_var.default_known:
            assert entry["default"] == code_var.default, f"{name}: default value mismatch"


def test_resources_have_valid_kind() -> None:
    contract = load_contract()
    resources = contract["resources"]
    assert isinstance(resources, dict)
    assert resources, "contract must declare at least one resource"
    for name, value in resources.items():
        assert isinstance(value, dict), f"{name}: resource entry must be a mapping"
        assert value["kind"] in {"Secret", "ConfigMap"}, f"{name}: kind must be Secret/ConfigMap"
