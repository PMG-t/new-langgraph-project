"""Define a simple chatbot agent.

This agent returns a predefined response without using an actual LLM.
"""

from typing import Any, Dict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph

from agent.configuration import Configuration
from agent.states.state import State

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from typing_extensions import TypedDict, Literal
from typing import Annotated
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, interrupt
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage
# from IPython.display import Image, display
from langchain_core.runnables.graph import CurveStyle, MermaidDrawMethod, NodeStyles
from langchain_core.messages import RemoveMessage


from agent.names import *
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