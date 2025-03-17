# DOC: Chatbot node and router

from typing_extensions import Literal
from langchain_openai import ChatOpenAI
from langgraph.graph import END

from ..names import *
from ..states import State
from .tools import demo_get_precipitation_data


tools = [
    demo_get_precipitation_data      # INFO: demo tool
]

llm = ChatOpenAI(model="gpt-3.5-turbo-0125").bind_tools(tools)


# DOC: chatbot node
def chatbot(state: State):
    return {"messages": [llm.invoke(state["messages"])]}


# DOC: chatbot router (conditional edge)
def chatbot_router(state: State) -> Literal[END, DEMO_GET_PRECIPITATION_DATA_TOOL_VALIDATOR]: # type: ignore
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
    if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
        # INFO: Check which tool is called (Only implementing first tool call) -> maybe next we can have a for-loop to handle each tool iteratively
        tool_calls = ai_message.tool_calls
        if tool_calls[0]['name'] == DEMO_GET_PRECIPITATION_DATA:
            next_node = DEMO_GET_PRECIPITATION_DATA_TOOL_VALIDATOR # INFO: prima di passare al tool passo al nodo che gestisce la chimata al tool
    return next_node