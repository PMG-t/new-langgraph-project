# DOC: Chatbot node and router

from typing_extensions import Literal

from langchain_core.messages import SystemMessage

from langgraph.graph import END
from langgraph.types import Command

from agent import utils
from agent.names import *
from agent.states import State
from agent.tools import (
    CDSForecastNotebookTool,
    SPICalculationNotebookTool,
    CodeEditorTool
)



cds_forecast_notebook_tool = CDSForecastNotebookTool()
spi_calculation_notebook_tool = SPICalculationNotebookTool()
base_code_editor_tool = CodeEditorTool()

multi_agent_tools = {
    cds_forecast_notebook_tool.name : cds_forecast_notebook_tool,
    spi_calculation_notebook_tool.name : spi_calculation_notebook_tool,
    base_code_editor_tool.name : base_code_editor_tool
}

llm_with_tools = utils._base_llm.bind_tools([tool for tool in multi_agent_tools.values()])



def chatbot(state: State) -> Command[Literal[END, CDS_FORECAST_SUBGRAPH, SPI_CALCULATION_SUBGRAPH, CODE_EDITOR_SUBGRAPH]]:     # type: ignore
    state["messages"] = state.get("messages", [])
    
    ai_message = llm_with_tools.invoke(state["messages"])
    
    if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
        
        # DOC: get the first tool call, discard others
        tool_call = ai_message.tool_calls[0]
        ai_message.tool_calls = [tool_call] 
        
        if tool_call['name'] == cds_forecast_notebook_tool.name:
            return Command(goto=CDS_FORECAST_SUBGRAPH, update = { "messages": [ ai_message ] })
        elif tool_call['name'] == spi_calculation_notebook_tool.name:
            return Command(goto=SPI_CALCULATION_SUBGRAPH, update = { "messages": [ ai_message ] })
        elif tool_call['name'] == base_code_editor_tool.name:
            return Command(goto=CODE_EDITOR_SUBGRAPH, update = { "messages": [ ai_message ] })

    return Command(goto=END, update = { "messages": [ ai_message ], "requested_agent": None, "nodes_params": dict() })