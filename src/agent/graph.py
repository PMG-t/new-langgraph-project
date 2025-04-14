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
    # chatbot_router,
    
    cds_ingestor_subgraph, 
    
    spi_calculation_subgraph
)


# DOC: define state
graph_builder = StateGraph(State)


# DOC: define nodes

graph_builder.add_node(chatbot)

graph_builder.add_node(CDS_FORECAST_SUBGRAPH, cds_ingestor_subgraph)

graph_builder.add_node(SPI_CALCULATION_SUBGRAPH, spi_calculation_subgraph)


# DOC: define edges

graph_builder.add_edge(START, CHATBOT)
# graph_builder.add_conditional_edges(CHATBOT, chatbot_router)

graph_builder.add_edge(CDS_FORECAST_SUBGRAPH, CHATBOT)

graph_builder.add_edge(SPI_CALCULATION_SUBGRAPH, CHATBOT)

# DOC: build graph
memory = MemorySaver()
graph = graph_builder.compile(checkpointer=memory)
graph.name = GRAPH