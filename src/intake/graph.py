from typing import Literal

from langgraph.graph import StateGraph, State
from typing import TypedDict, Optional


class IntakeState(TypedDict):
    user_id: str
    current_step: str
    business_name: Optional[str]
    industry: Optional[str]
    revenue_range: Optional[str]
    team_size: Optional[str]
    location: Optional[str]
    pain_points: Optional[str]
    goals: Optional[str]
    last_message: Optional[str]
    last_activity: Optional[str]


def build_intake_graph():
    workflow = StateGraph(IntakeState)
    return workflow.compile()
