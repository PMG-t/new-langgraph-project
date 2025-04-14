# DOC: Chatbot node and router

from typing_extensions import Literal

from langchain_core.messages import SystemMessage

from langgraph.graph import END
from langgraph.types import Command

from agent import utils
from agent.names import *
from agent.states import State
from agent.tools import (
    CDSForecastNotebookTool, CDSForecastCodeEditorTool,
    SPICalculationNotebookTool, SPICalculationCodeEditorTool
)



cds_forecast_notebook_tool = CDSForecastNotebookTool()
cds_forecast_code_editor_tool = CDSForecastCodeEditorTool()
spi_calculation_notebook_tool = SPICalculationNotebookTool()
spi_calculation_code_editor_tool = SPICalculationCodeEditorTool()

multi_agent_tools = {
    cds_forecast_notebook_tool.name : cds_forecast_notebook_tool,
    cds_forecast_code_editor_tool.name : cds_forecast_code_editor_tool,
    spi_calculation_notebook_tool.name : spi_calculation_notebook_tool,
    spi_calculation_code_editor_tool.name : spi_calculation_code_editor_tool 
}

llm_with_tools = utils._base_llm.bind_tools([tool for tool in multi_agent_tools.values()])



def chatbot(state: State) -> Command[Literal[END, CDS_FORECAST_SUBGRAPH, SPI_CALCULATION_SUBGRAPH]]:     # type: ignore
    state["messages"] = state.get("messages", [])
    
    ai_message = llm_with_tools.invoke(state["messages"])
    
    if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
        for tool_call in ai_message.tool_calls:
            if tool_call['name'] == cds_forecast_notebook_tool.name or tool_call['name'] == cds_forecast_code_editor_tool.name:
                return Command(goto=CDS_FORECAST_SUBGRAPH, update = { "messages": [ ai_message ] })
            elif tool_call['name'] == cds_forecast_notebook_tool.name or tool_call['name'] == cds_forecast_code_editor_tool.name:
                return Command(goto=SPI_CALCULATION_SUBGRAPH, update = { "messages": [ ai_message ] })

    return Command(goto=END, update = { "messages": [ ai_message ], "requested_agent": None, "nodes_params": dict() })