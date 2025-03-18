"""
Defining agent graph
"""

from langgraph.graph import StateGraph
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from agent.names import *

from agent.configuration import Configuration
from agent.states.state import State

from agent.nodes import chatbot
from agent.nodes import chatbot_router
from agent.nodes import demo_get_precipitation_data_tool_validator
from agent.nodes import demo_get_precipitation_data_tool_runner


# DOC: define state
graph_builder = StateGraph(State)

# DOC: define nodes
graph_builder.add_node(chatbot)
graph_builder.add_node(demo_get_precipitation_data_tool_validator)
graph_builder.add_node(demo_get_precipitation_data_tool_runner)

# DOC: define edges
graph_builder.add_edge(START, CHATBOT)
graph_builder.add_conditional_edges(CHATBOT, chatbot_router)
graph_builder.add_edge(DEMO_GET_PRECIPITATION_DATA_TOOL_RUNNER, CHATBOT)

# DOC: build graph
memory = MemorySaver()
graph = graph_builder.compile(checkpointer=memory)
graph.name = GRAPH