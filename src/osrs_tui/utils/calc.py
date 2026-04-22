"""
utils/calc.py - Domain models and pure functions for the Skill Calculator.

Keeping all logic here (separate from the Textual screen) makes it easy to:
    - Unit test calculations without a TUI
    - Serialize a CalcSession and pass it to the future Resource Cost screen 
    - Extend with GE price data later without touching screen code
"""

from __future__ import annotations

import importlib.resources
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from osrs_tui.utils.api import _XP_TABLE


# ----------------------------------------------------------
# Actions database
# ----------------------------------------------------------

def load_actions(skill: str) -> list["TrainingAction"]:
    """Load all training actions for `skill` from the bundled JSON database."""
    data_path = Path(__file__).parent / "data" / "actions.json"
    with open(data_path) as f:
        raw = json.load(f)
    return [TrainingAction(**entry) for entry in raw.get(skill, [])]


@dataclass
class InputMaterial:
    name: str
    qty: float
    stackable: bool = False


@dataclass
class OutputMaterial:
    name: str
    qty: float
    rarity: float = 1.0
    stackable: bool = False


@dataclass
class SkillTool:
    name: str
    qty: float
    level_req: int = 1


@dataclass
class PreRollOutputMaterial:
    name: str
    qty: float
    rarity: float
    stackable: bool = False


@dataclass
class TrainingAction:
    name: str
    level_req: int
    xp: float
    members: bool
    inputs: list[dict]
    tools: list[dict]
    outputs: list[dict]
    pre_roll_outputs: list[dict]

    def input_materials(self) -> list[InputMaterial]:
        return [InputMaterial(i["name"], i["qty"], i["stackable"]) for i in self.inputs if i.get("qty", 0) > 0]
    
    def skill_tools(self) -> list[SkillTool]:
        return [SkillTool(t["name"], t["qty"], t["level_req"]) for t in self.tools if t.get("qty", 0) > 0]
    
    def output_materials(self) -> list[OutputMaterial]:
        return [OutputMaterial(o["name"], o["qty"], o["rarity"], o["stackable"]) for o in self.outputs if o.get("qty", 0) > 0]
    
    def pre_rolls(self) -> list[PreRollOutputMaterial]:
        return [PreRollOutputMaterial(**o) for o in self.pre_roll_outputs if o.get("qty", 0) > 0]
    

# ----------------------------------------------------------
# Calculation session - the object that gets passed to external utility screens
# ----------------------------------------------------------

@dataclass
class CalcSession:
    """
    Fully describes one skill-calculator configuration.
    Serializable to dict for passing between screens.
    """
    skill: str
    start_xp: int
    target_xp: int
    selected_actions: list[str] = field(default_factory=list)

    results: list["ActionResult"] = field(default_factory=list)

    @property
    def xp_needed(self) -> int:
        return max(0, self.target_xp - self.start_xp)
    
    @property
    def start_level(self) -> int:
        return self._xp_to_level(self.start_xp)
    
    @property
    def target_level(self) -> int:
        return self._xp_to_level(self.target_xp)
    
    def to_dict(self) -> dict:
        """Lightweight serialization for inter-screen passing."""
        return {
            "skill": self.skill,
            "start_xp": self.start_xp,
            "target_xp": self.target_xp,
            "selected_actions": self.selected_actions
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "CalcSession":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
    
    @staticmethod
    def _xp_to_level(xp: int) -> int:
        level = 1
        for i, threshold in enumerate(_XP_TABLE, start=1):
            if xp >= threshold:
                level = i
            else:
                break
        return min(level, 99)
    
    @staticmethod
    def _level_to_xp(level: int) -> int:
        if level <= 1:
            return 0
        if level > 99:
            return 200_000_000
        return _XP_TABLE[level - 1]
    

@dataclass
class ActionResult:
    action: TrainingAction
    actions_needed: int

    @property
    def total_xp(self) -> float:
        return self.actions_needed * self.action.xp
    
    def material_totals(self) -> list[InputMaterial]:
        """Scale input materials by `actions_needed`."""
        return [
            InputMaterial(
                m.name,
                math.ceil(m.qty * self.actions_needed)
            )
            for m in self.action.input_materials()
        ]
    

def calculate(session: CalcSession, all_actions: list[TrainingAction]) -> list[ActionResult]:
    action_map = {a.name: a for a in all_actions}
    results = []
    for name in session.selected_actions:
        if name not in action_map:
            continue
        action = action_map[name]
        needed = math.ceil(session.xp_needed / action.xp) if action.xp > 0 else 0
        results.append(ActionResult(action=action, actions_needed=needed))
    return results

