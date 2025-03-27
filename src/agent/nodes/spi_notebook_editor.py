# DOC: Edit SPI notebook

import json

from typing_extensions import Literal
from langgraph.types import Command
from langchain_core.messages import RemoveMessage

from ..names import *
from ..states import State
from ..tools import spi_notebook_editor



def spi_notebook_editor_tool_validator(state: State) -> Command[Literal[CHATBOT, SPI_NOTEBOOK_EDITOR_TOOL_RUNNER]]: # type: ignore
    tool_message = state["messages"][-1]
    tool_call = tool_message.tool_calls[-1]
    
    is_notebook_specified = 'notebook_path' in tool_call['args'] and tool_call['args']['notebook_path'] not in [None, ""]
    is_code_specified = 'code_request' in tool_call['args'] and tool_call['args']['code_request'] not in [None, "", []]
    
    if is_notebook_specified and is_code_specified:
        return Command(goto=SPI_NOTEBOOK_EDITOR_TOOL_RUNNER, update={"messages": [tool_message]})
    
    elif not is_notebook_specified:
        rem_msg = [RemoveMessage(id=tool_message.id)]
        sys_message = f"""
            L\'utente a rihiesto di eseguire il tool {tool_call["name"]} con  questi argomenti:
            - notebook_path: NULL
            - code_request: {tool_call['args']['code_request'] if is_code_specified else "NULL"}
            Non ha specificato il percorso del notebook. Chiediglielo.
        """
        feedback_message = {"role": "system", "content": sys_message}
        return Command(goto=CHATBOT, update={"messages": rem_msg + [feedback_message]})
    
    elif not is_code_specified:
        rem_msg = [RemoveMessage(id=tool_message.id)]
        sys_message = f"""
            L\'utente a rihiesto di eseguire il tool {tool_call["name"]} con  questi argomenti:
            - notebook_path: {tool_call['args']['notebook_path']}
            - code_request: NULL
            Non ha specificato che codice aggiungere al notebook. Chiediglielo.
        """
        feedback_message = {"role": "system", "content": sys_message}
        return Command(goto=CHATBOT, update={"messages": rem_msg + [feedback_message]})
    
    else:
        print('Non OK!')
        rem_msg = [RemoveMessage(id=tool_message.id)]
        return Command(goto=CHATBOT, update={"messages": rem_msg + [feedback_message]})
    
    
    
    
def spi_notebook_editor_tool_runner(state):
    new_messages = []
    tools = {SPI_NOTEBOOK_EDITOR: spi_notebook_editor}
    tool_calls = state["messages"][-1].tool_calls
    for tool_call in tool_calls:
        # if tool_call["name"] in tools:
        tool = tools[tool_call["name"]]
        result = tool.invoke(tool_call["args"])
        new_messages.append(
            {
                "role": "tool",
                "name": tool_call["name"],
                "content": result,
                "tool_call_id": tool_call["id"],
            }
        )
    return {"messages": new_messages}