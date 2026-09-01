from dataclasses import dataclass, field
from pathlib import Path

import yaml

SCENARIOS_DIR = Path("data/scenarios")


@dataclass
class Step:
    id: str
    type: str
    content: dict[str, str]
    options: dict[str, list[str]] = field(default_factory=dict)
    answer: int | None = None
    next: dict[str, str] = field(default_factory=dict)
    retry: dict[str, str] = field(default_factory=dict)


@dataclass
class Scenario:
    id: str
    title: dict[str, str]
    order: int
    roles: list[str]
    steps: dict[str, Step]


def _str(value: object) -> str:
    return str(value)


def _str_dict(value: object | None) -> dict[str, str]:
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items()}
    return {}


def _list_str(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if isinstance(v, str)]
    return []


def _int(value: object, default: int = 0) -> int:
    return value if isinstance(value, int) else default


def _opt_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _load_scenario(path: Path) -> Scenario:
    raw: dict[str, object] = yaml.safe_load(path.read_text(encoding="utf-8"))

    steps: dict[str, Step] = {}
    raw_steps = raw.get("steps", [])
    assert isinstance(raw_steps, list)
    for raw_step in raw_steps:
        assert isinstance(raw_step, dict)
        step = Step(
            id=_str(raw_step["id"]),
            type=_str(raw_step.get("type", "")),
            content={
                "pl": _str(raw_step.get("content_pl", "")),
                "en": _str(raw_step.get("content_en", "")),
            },
            options={
                "pl": _list_str(raw_step.get("options_pl", [])),
                "en": _list_str(raw_step.get("options_en", [])),
            },
            answer=_opt_int(raw_step.get("answer")),
            next={
                "pl": _str(raw_step.get("next_pl", "")),
                "en": _str(raw_step.get("next_en", "")),
            },
            retry={
                "pl": _str(raw_step.get("retry_pl", "")),
                "en": _str(raw_step.get("retry_en", "")),
            },
        )
        steps[step.id] = step

    return Scenario(
        id=_str(raw["id"]),
        title={
            "pl": _str(raw.get("title_pl", "")),
            "en": _str(raw.get("title_en", "")),
        },
        order=_int(raw.get("order")),
        roles=_list_str(raw.get("roles", [])),
        steps=steps,
    )


_scenarios: list[Scenario] | None = None


def load_scenarios() -> list[Scenario]:
    global _scenarios
    if _scenarios is None:
        _scenarios = [_load_scenario(path) for path in sorted(SCENARIOS_DIR.glob("*.yaml"))]
    return _scenarios


def get_scenario(scenario_id: str) -> Scenario | None:
    for scenario in load_scenarios():
        if scenario.id == scenario_id:
            return scenario
    return None


def get_scenarios_for_role(role: str) -> list[Scenario]:
    return [scenario for scenario in load_scenarios() if role in scenario.roles]
