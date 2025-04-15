from typing_extensions import Literal

from langgraph.graph import StateGraph
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

from agent import utils
from agent.names import *
from agent.states.state import State
from agent.tools import CDSForecastNotebookTool
from agent.nodes import BaseToolHandlerNode, BaseToolInterruptNode



# DOC: CDS-Forecast subgraph - Exploit I-Cisk API to ingest CDS data. Data could be related to 'Temperature', 'Seasonal forecast', 'Glofas'



cds_forecast_notebook_tool = CDSForecastNotebookTool()
cds_forecast_tools_dict = {
    cds_forecast_notebook_tool.name: cds_forecast_notebook_tool
}
cds_tool_names = list(cds_forecast_tools_dict.keys())
cds_tools = list(cds_forecast_tools_dict.values())

llm_with_cds_tools = utils._base_llm.bind_tools(cds_tools)



# DOC: This is for store some information that could be util for the nodes in the subgraph. N.B. Keys are node names, values are a custom dict
class CDSState(State):
    nodes_params: dict
        


# DOC: Base tool handler: runs the tool, if tool interrupt go to interrupt node handler
cds_forecast_tool_handler = BaseToolHandlerNode(
    state = CDSState,
    tool_handler_node_name = CDS_FORECAST_TOOL_HANDLER,
    tool_interrupt_node_name = CDS_FORECAST_TOOL_INTERRUPT,
    tools = cds_forecast_tools_dict,
    additional_ouput_state = { 'requested_agent': None, 'nodes_params': dict() }
)


# DOC: Base tool interrupt node: handle tool interrupt by type and go back to tool hndler with updatet state to rerun tool
cds_forecast_tool_interrupt = BaseToolInterruptNode(
    state = CDSState,
    tool_handler_node_name = CDS_FORECAST_TOOL_HANDLER,
    tool_interrupt_node_name = CDS_FORECAST_TOOL_INTERRUPT,
    tools = cds_forecast_tools_dict,
    custom_tool_interupt_handlers = dict()     # DOC: use default 
)
    
    
    
# DOC: State
cds_ingestor_graph_builder = StateGraph(CDSState)

# DOC: Nodes

cds_ingestor_graph_builder.add_node(CDS_FORECAST_TOOL_HANDLER, cds_forecast_tool_handler)
cds_ingestor_graph_builder.add_node(CDS_FORECAST_TOOL_INTERRUPT, cds_forecast_tool_interrupt)

# DOC: Edges
cds_ingestor_graph_builder.add_edge(START, CDS_FORECAST_TOOL_HANDLER)

# DOC: Compile
cds_ingestor_subgraph = cds_ingestor_graph_builder.compile()
cds_ingestor_subgraph.name = CDS_FORECAST_SUBGRAPH