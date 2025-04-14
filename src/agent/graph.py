"""
Defining agent graph
"""

from langgraph.graph import StateGraph
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from agent.names import *

from agent.configuration import Configuration
from agent.states.state import State

from agent.nodes import (
    chatbot, 
    
    cds_ingestor_subgraph, 
    spi_calculation_subgraph,
    code_editor_subgraph
)


# DOC: define state
graph_builder = StateGraph(State)


# DOC: define nodes

graph_builder.add_node(chatbot)

graph_builder.add_node(CDS_FORECAST_SUBGRAPH, cds_ingestor_subgraph)

graph_builder.add_node(SPI_CALCULATION_SUBGRAPH, spi_calculation_subgraph)

graph_builder.add_node(CODE_EDITOR_SUBGRAPH, code_editor_subgraph)


# DOC: define edges

graph_builder.add_edge(START, CHATBOT)

graph_builder.add_edge(CDS_FORECAST_SUBGRAPH, CHATBOT)

graph_builder.add_edge(SPI_CALCULATION_SUBGRAPH, CHATBOT)

graph_builder.add_edge(CODE_EDITOR_SUBGRAPH, CHATBOT)

# DOC: build graph
memory = MemorySaver()
graph = graph_builder.compile(checkpointer=memory)
graph.name = GRAPH