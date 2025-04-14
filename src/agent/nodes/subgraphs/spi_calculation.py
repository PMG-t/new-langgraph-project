from typing_extensions import Literal

from langgraph.graph import StateGraph
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

from agent import utils
from agent.names import *
from agent.states.state import State
from agent.tools import SPICalculationNotebookTool
from agent.nodes import BaseToolHandlerNode, BaseToolInterruptNode



# DOC: This node is responsible for calculating the SPI (Standardized Precipitation Index) using the provided data and building a jupyter notebook for visualization.



spi_calculation_notebook_tool = SPICalculationNotebookTool()
spi_calculation_tools_dict = {
    spi_calculation_notebook_tool.name: spi_calculation_notebook_tool
}
spi_tool_names = list(spi_calculation_tools_dict.keys())
spi_tools = list(spi_calculation_tools_dict.values())

llm_with_spi_tools = utils._base_llm.bind_tools(spi_tools)



# DOC: This is for store some information that could be util for the nodes in the subgraph. N.B. Keys are node names, values are a custom dict
class SPIState(State):
    nodes_params: dict
    
    

# DOC: Base tool handler: runs the tool, if tool interrupt go to interrupt node handler
spi_calculation_tool_handler = BaseToolHandlerNode(
    state = SPIState,
    tool_handler_node_name = SPI_CALCULATION_TOOL_HANDLER,
    tool_interrupt_node_name = SPI_CALCULATION_TOOL_INTERRUPT,
    tools = spi_calculation_tools_dict,
    additional_ouput_state = { 'requested_agent': None, 'nodes_params': dict() }
)


# DOC: Base tool interrupt node: handle tool interrupt by type and go back to tool hndler with updatet state to rerun tool
spi_calculation_tool_interrupt = BaseToolInterruptNode(
    state = SPIState,
    tool_handler_node_name = SPI_CALCULATION_TOOL_HANDLER,
    tool_interrupt_node_name = SPI_CALCULATION_TOOL_INTERRUPT,
    tools = spi_calculation_tools_dict,
    tool_interupt_handlers = dict()     # DOC: use default 
)



# DOC: State
spi_calculation_graph_builder = StateGraph(SPIState)

# DOC: Nodes
spi_calculation_graph_builder.add_node(SPI_CALCULATION_TOOL_HANDLER, spi_calculation_tool_handler)
spi_calculation_graph_builder.add_node(SPI_CALCULATION_TOOL_INTERRUPT, spi_calculation_tool_interrupt)

# DOC: Edges
spi_calculation_graph_builder.add_edge(START, SPI_CALCULATION_TOOL_HANDLER)

# DOC: Compile
spi_calculation_subgraph = spi_calculation_graph_builder.compile()
spi_calculation_subgraph.name = SPI_CALCULATION_SUBGRAPH