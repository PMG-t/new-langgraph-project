# DOC: Demo get precipitation data node

from typing_extensions import Literal
from langgraph.types import Command
from langchain_core.messages import RemoveMessage

from ..names import *
from ..states import State
from .tools import demo_get_precipitation_data



def demo_get_precipitation_data_tool_validator(state: State) -> Command[Literal[CHATBOT, DEMO_GET_PRECIPITATION_DATA_TOOL_RUNNER]]: # type: ignore
    tool_message = state["messages"][-1]
    tool_call = tool_message.tool_calls[-1]
    is_location_specified = 'location' in tool_call['args'] and tool_call['args']['location'] not in [None, ""]
    is_date_specified = 'date' in tool_call['args'] and tool_call['args']['date'] not in [None, ""]
    
    if is_location_specified and is_date_specified:
        return Command(goto=DEMO_GET_PRECIPITATION_DATA_TOOL_RUNNER)
    
    elif not (is_location_specified or is_date_specified):
        rem_msg = [RemoveMessage(id=tool_message.id)]
        sys_message = f'L\'utente a rihiesto di eseguire il tool {tool_call["name"]} ma non ha specificato nè la location nè la data. Chiedigliele.'
        feedback_message = {"role": "system", "content": sys_message}
        return Command(goto=CHATBOT, update={"messages": rem_msg + [feedback_message]})
    
    elif not is_location_specified:
        rem_msg = [RemoveMessage(id=tool_message.id)]
        sys_message = f"""
            L\'utente a rihiesto di eseguire il tool {tool_call["name"]} con  questi argomenti:
            - location: NULL
            - date: {tool_call['args']['date']}
            Non ha specificato la location. Chiedigliela.
        """
        feedback_message = {"role": "system", "content": sys_message}
        return Command(goto=CHATBOT, update={"messages": rem_msg + [feedback_message]})
    
    elif not is_date_specified:
        rem_msg = [RemoveMessage(id=tool_message.id)]
        sys_message = f"""
            L\'utente a rihiesto di eseguire il tool {tool_call["name"]} con  questi argomenti:
            - location: {tool_call['args']['location']}
            - date: NULL.
            Non ha specificato la data. Chiedigliela.
        """
        feedback_message = {"role": "system", "content": sys_message}
        return Command(goto=CHATBOT, update={"messages": rem_msg + [feedback_message]})
    
    else:
        print('Non OK!')
        rem_msg = [RemoveMessage(id=tool_message.id)]
        return Command(goto=CHATBOT, update={"messages": rem_msg + [feedback_message]})
    
    

def demo_get_precipitation_data_tool_runner(state):
    new_messages = []
    tools = {DEMO_GET_PRECIPITATION_DATA: demo_get_precipitation_data}
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