from __future__ import annotations

# Expose a LangGraph graph for CLI/server usage
# This leverages the prebuilt ReAct agent created in the package.
from codeu import create_coding_agent

# The variable name `graph` is required by langgraph.json configuration
# It should be a Runnable/Graph compiled by LangGraph prebuilt helper.
graph = create_coding_agent()