from typing_extensions import Literal

from langgraph.graph import StateGraph
from langgraph.graph import StateGraph, START, END

from agent import utils
from agent.names import *
from agent.states.state import State
from agent.tools import CDSIngestorForecastTool, CDSForecastIngestorCodeEditorTool
from agent.nodes import BaseToolHandlerNode, BaseToolInterruptNode



# DOC: CDS-Ingestor subgraph - Exploit I-Cisk API to ingest CDS data. Data could be related to 'Temperature', 'Seasonal forecast', 'Glofas'



cds_forecast_ingestor_tool = CDSIngestorForecastTool()
cds_forecast_ingestor_tool_code_editor = CDSForecastIngestorCodeEditorTool()

cds_tools_dict = {
    cds_forecast_ingestor_tool.name: cds_forecast_ingestor_tool,
    cds_forecast_ingestor_tool_code_editor.name: cds_forecast_ingestor_tool_code_editor
}
cds_tool_names = list(cds_tools_dict.keys())
cds_tools = list(cds_tools_dict.values())

llm_with_cds_tools = utils._base_llm.bind_tools(cds_tools)



# DOC: This is for store some information that could be util for the nodes in the subgraph. N.B. Keys are node names, values are a custom dict
class StateCdsIngestor(State):
    nodes_params: dict
    
        

# DOC: CDS chatbot [NODE]
def cds_chatbot(state: StateCdsIngestor):
    ai_message = llm_with_cds_tools.invoke(state["messages"])
    return {"messages": [ai_message]}


# DOC: CDS chatbot-router [NODE]
def cds_chatbot_router(state: StateCdsIngestor) -> Literal[END, CDS_INGESTOR_FORECAST_TOOL_HANDLER]:     # type: ignore
    """
    Use in the conditional_edge to route to the ToolNode if the last message has tool calls. Otherwise, route to the end.
    """
    
    next_node = END
    if isinstance(state, list):
        ai_message = state[-1]
    elif messages := state.get("messages", []):
        ai_message = messages[-1]
    else:
        raise ValueError(f"No messages found in input state to tool_edge: {state}")
    
    print(f'\n\n\n TOOL CALLS {ai_message.tool_calls} \n\n\n')
    
    if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
        next_node = CDS_INGESTOR_FORECAST_TOOL_HANDLER
    
    return next_node



# DOC: Base tool handler: runs the tool, if tool interrupt go to interrupt node handler
cds_forecast_tool_handler = BaseToolHandlerNode(
    state = StateCdsIngestor,
    tool_handler_node_name = CDS_INGESTOR_FORECAST_TOOL_HANDLER,
    tool_interrupt_node_name = CDS_FORECAST_TOOL_INTERRUPT,
    tools = cds_tools_dict,
    additional_ouput_state = { 'requested_agent': None, 'nodes_params': dict() }
)


# DOC: Base tool interrupt node: handle tool interrupt by type and go back to tool hndler with updatet state to rerun tool
cds_forecast_tool_interrupt = BaseToolInterruptNode(
    state = StateCdsIngestor,
    tool_handler_node_name = CDS_INGESTOR_FORECAST_TOOL_HANDLER,
    tool_interrupt_node_name = CDS_FORECAST_TOOL_INTERRUPT,
    tools = cds_tools_dict,
    tool_interupt_handlers = dict()     # DOC: use default 
)
    
    
    
# DOC: State
cds_temperature_graph_builder = StateGraph(StateCdsIngestor)

# DOC: Nodes
cds_temperature_graph_builder.add_node(CDS_CHATBOT, cds_chatbot)

cds_temperature_graph_builder.add_node(CDS_INGESTOR_FORECAST_TOOL_HANDLER, cds_forecast_tool_handler)
cds_temperature_graph_builder.add_node(CDS_FORECAST_TOOL_INTERRUPT, cds_forecast_tool_interrupt)

# DOC: Edges
cds_temperature_graph_builder.add_edge(START, CDS_CHATBOT)
cds_temperature_graph_builder.add_conditional_edges(CDS_CHATBOT, cds_chatbot_router)

# DOC: Compile
cds_temperature_subgraph = cds_temperature_graph_builder.compile()
cds_temperature_subgraph.name = CDS_INGESTOR_FORECAST_SUBGRAPH