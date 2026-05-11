"""Polishing Graph 模块 - 多阶润色流"""

from app.graph.polishing.builder import get_polishing_graph
from app.graph.polishing.debate import (
    DebateState,
    author_node,
    editor_node,
    finalize_debate_node,
    get_debate_graph,
    increment_iteration_node,
    should_continue_debate,
)
from app.graph.polishing.nodes import (
    fact_checker_node,
    formatter_node,
    route_by_mode,
    router_node,
)
from app.graph.polishing.state import (
    DebateRound,
    PolishingState,
    ScoreDetail,
)

__all__ = [
    # State
    "PolishingState",
    "DebateState",
    "ScoreDetail",
    "DebateRound",
    # Polishing Nodes
    "router_node",
    "formatter_node",
    "fact_checker_node",
    # Debate Nodes
    "author_node",
    "editor_node",
    "increment_iteration_node",
    "finalize_debate_node",
    # Conditional Edges
    "route_by_mode",
    "should_continue_debate",
    # Graphs
    "get_debate_graph",
    "get_polishing_graph",
]
