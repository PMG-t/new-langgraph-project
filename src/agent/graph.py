"""Define a simple chatbot agent.

This agent returns a predefined response without using an actual LLM.
"""

from typing import Any, Dict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph

from agent.configuration import Configuration
from agent.states.state import State

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from typing_extensions import TypedDict, Literal
from typing import Annotated
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, interrupt
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage
# from IPython.display import Image, display
from langchain_core.runnables.graph import CurveStyle, MermaidDrawMethod, NodeStyles
from langchain_core.messages import RemoveMessage


from agent.names import *
from agent.nodes import chatbot
from agent.nodes import chatbot_router
from agent.nodes import demo_get_precipitation_data_tool_validator
from agent.nodes import demo_get_precipitation_data_tool_runner



graph_builder = StateGraph(State)

graph_builder.add_node(chatbot)
graph_builder.add_node(demo_get_precipitation_data_tool_validator)
graph_builder.add_node(demo_get_precipitation_data_tool_runner)

graph_builder.add_edge(START, CHATBOT)
graph_builder.add_conditional_edges(CHATBOT, chatbot_router)
graph_builder.add_edge(DEMO_GET_PRECIPITATION_DATA_TOOL_RUNNER, CHATBOT)

memory = MemorySaver()

graph = graph_builder.compile(checkpointer=memory)

graph.name = GRAPH


# import datetime


# @tool()
# def get_precipitation_data(location: str = None, date: str = None):
#     """
#     Get the precipitation intenisity measures in millimeters per hour for a given location in a specified date.
#     Use this tool when user asks for precipitation data even if user does not provide location and date.
    

#     Args:
#         location: location name
#         date: date in format YYYY-MM-DD
#     """
#     return len(location) + datetime.datetime.strptime(date, "%Y-%m-%d").date().day


# tools = [get_precipitation_data]

# llm = ChatOpenAI(model="gpt-3.5-turbo-0125").bind_tools(tools)


# def chatbot(state: State):
#     return {"messages": [llm.invoke(state["messages"])]}

# def chatbot_router(state: State) -> Literal[END, "demo_get_precipitation_data_tool_validator"]:
#     """
#     Use in the conditional_edge to route to the ToolNode if the last message has tool calls. Otherwise, route to the end.
#     """
#     next_node = END
#     if isinstance(state, list):
#         ai_message = state[-1]
#     elif messages := state.get("messages", []):
#         ai_message = messages[-1]
#     else:
#         raise ValueError(f"No messages found in input state to tool_edge: {state}")
#     if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
#         # INFO: Check which tool is called (Only implementing first tool call) -> maybe next we can have a for-loop to handle each tool iteratively
#         tool_calls = ai_message.tool_calls
#         if tool_calls[0]['name'] == "get_precipitation_data":
#             next_node = "demo_get_precipitation_data_tool_validator" # INFO: prima di passare al tool passo al nodo che gestisce la chimata al tool
#     return next_node

# def demo_get_precipitation_data_tool_validator(state: State) -> Command[Literal["chatbot", "demo_get_precipitation_data_tool_runner"]]:
#     tool_message = state["messages"][-1]
#     tool_call = tool_message.tool_calls[-1]
#     # print('###')
#     # pprint(state)
#     # print('###')
#     is_location_specified = 'location' in tool_call['args'] and tool_call['args']['location'] not in [None, ""]
#     is_date_specified = 'date' in tool_call['args'] and tool_call['args']['date'] not in [None, ""]
#     if is_location_specified and is_date_specified:
#         print('OK!')
#         return Command(goto="demo_get_precipitation_data_tool_runner")
#     elif not (is_location_specified or is_date_specified):
#         print('Missing location and date!')
#         rem_msg = [RemoveMessage(id=tool_message.id)]
#         # request_location_and_date = interrupt(
#         #     {
#         #         "question": "Serve una location e una data",
#         #         # Surface tool calls for review
#         #         "tool_call": tool_call,
#         #     }
#         # )
#         # location_and_date = request_location_and_date.get('data')
#         # sys_message = f'Alla richiesta di inserimento di una location e una data l\'utente ha risposto con: "{location_and_date}"'
#         # feedback_message = {"role": "system", "content": sys_message}
#         # return Command(goto="chatbot", update={"messages": rem_msg + [feedback_message]})
        
#         sys_message = f'L\'utente a rihiesto di eseguire il tool {tool_call["name"]} ma non ha specificato nè la location nè la data. Chiedigliele.'
#         feedback_message = {"role": "system", "content": sys_message}
        
#         return Command(goto="chatbot", update={"messages": rem_msg + [feedback_message]})
#     elif not is_location_specified:
#         print('missing location!')
#         rem_msg = [RemoveMessage(id=tool_message.id)]
#         # request_location = interrupt(
#         #     {
#         #         "question": "Serve una location",
#         #         # Surface tool calls for review
#         #         "tool_call": tool_call,
#         #     }
#         # )
#         # location = request_location.get('data')
#         # sys_message = f'Alla richiesta di inserimento di una location l\'utente ha risposto con: "{location}"'
#         sys_message = f"""
#             L\'utente a rihiesto di eseguire il tool {tool_call["name"]} con  questi argomenti:
#             - location: NULL
#             - date: {tool_call['args']['date']}
#             Non ha specificato la location. Chiedigliela.
#         """
        
#         feedback_message = {"role": "system", "content": sys_message}
#         return Command(goto="chatbot", update={"messages": rem_msg + [feedback_message]})
#     elif not is_date_specified:
#         print('missing date!')
#         rem_msg = [RemoveMessage(id=tool_message.id)]
#         # request_location = interrupt(
#         #     {
#         #         "question": "Serve una data",
#         #         # Surface tool calls for review
#         #         "tool_call": tool_call,
#         #     }
#         # )
#         # date = request_location.get('data')
#         # sys_message = f'Alla richiesta di inserimento di una data l\'utente ha risposto con: "{date}"' # 
#         sys_message = f"""
#             L\'utente a rihiesto di eseguire il tool {tool_call["name"]} con  questi argomenti:
#             - location: {tool_call['args']['location']}
#             - date: NULL.
#             Non ha specificato la data. Chiedigliela.
#         """
#         feedback_message = {"role": "system", "content": sys_message}
#         return Command(goto="chatbot", update={"messages": rem_msg + [feedback_message]})
#     else: 
#         print('Non OK!')
#         rem_msg = [RemoveMessage(id=tool_message.id)]
#         return Command(goto="chatbot", update={"messages": rem_msg + [feedback_message]})

# def demo_get_precipitation_data_tool_validator_OLD(state: State) -> Command[Literal["chatbot", "demo_get_precipitation_data_tool_runner"]]:
#     tool_message = state["messages"][-1]
#     tool_call = tool_message.tool_calls[-1]
#     # print('###')
#     # pprint(state)
#     # print('###')
#     is_location_specified = 'location' in tool_call['args'] and tool_call['args']['location'] not in [None, ""]
#     is_date_specified = 'date' in tool_call['args'] and tool_call['args']['date'] not in [None, ""]
#     if is_location_specified and is_date_specified:
#         # print('OK!')
#         return Command(goto="demo_get_precipitation_data_tool_runner")
#     elif not (is_location_specified or is_date_specified):
#         # print('Missing location and date!')
#         rem_msg = [RemoveMessage(id=tool_message.id)]
#         request_location_and_date = interrupt(
#             {
#                 "question": "Serve una location e una data",
#                 # Surface tool calls for review
#                 "tool_call": tool_call,
#             }
#         )
#         location_and_date = request_location_and_date #.get('data')
#         sys_message = f'Alla richiesta di inserimento di una location e una data l\'utente ha risposto con: "{location_and_date}"'
#         feedback_message = {"role": "system", "content": sys_message}
#         return Command(goto="chatbot", update={"messages": rem_msg + [feedback_message]})
#     elif not is_location_specified:
#         # print('missing location!')
#         rem_msg = [RemoveMessage(id=tool_message.id)]
#         request_location = interrupt(
#             {
#                 "question": "Serve una location",
#                 # Surface tool calls for review
#                 "tool_call": tool_call,
#             }
#         )
#         location = request_location #.get('data')
#         sys_message = f'Alla richiesta di inserimento di una location l\'utente ha risposto con: "{location}"'
#         feedback_message = {"role": "system", "content": sys_message}
#         return Command(goto="chatbot", update={"messages": rem_msg + [feedback_message]})
#     elif not is_date_specified:
#         # print('missing date!')
#         rem_msg = [RemoveMessage(id=tool_message.id)]
#         request_location = interrupt(
#             {
#                 "question": "Serve una data",
#                 # Surface tool calls for review
#                 "tool_call": tool_call,
#             }
#         )
#         date = request_location #.get('data')
#         sys_message = f'Alla richiesta di inserimento di una data l\'utente ha risposto con: "{date}"' # 
#         feedback_message = {"role": "system", "content": sys_message}
#         return Command(goto="chatbot", update={"messages": rem_msg + [feedback_message]})
#     else: 
#         # print('Non OK!')
#         rem_msg = [RemoveMessage(id=tool_message.id)]
#         return Command(goto="chatbot", update={"messages": rem_msg + [feedback_message]})
        
# def demo_get_precipitation_data_tool_runner(state):
#     new_messages = []
#     tools = {"get_precipitation_data": get_precipitation_data}
#     tool_calls = state["messages"][-1].tool_calls
#     for tool_call in tool_calls:
#         # if tool_call["name"] in tools:
#         tool = tools[tool_call["name"]]
#         result = tool.invoke(tool_call["args"])
#         new_messages.append(
#             {
#                 "role": "tool",
#                 "name": tool_call["name"],
#                 "content": result,
#                 "tool_call_id": tool_call["id"],
#             }
#         )
#     return {"messages": new_messages}






# async def my_node(state: State, config: RunnableConfig) -> Dict[str, Any]:
#     """Each node does work."""
#     configuration = Configuration.from_runnable_config(config)
#     # configuration = Configuration.from_runnable_config(config)
#     # You can use runtime configuration to alter the behavior of your
#     # graph.
#     return {
#         "changeme": "output from my_node. "
#         f"Configured with {configuration.my_configurable_param}"
#     }





# # Define a new graph
# workflow = StateGraph(State, config_schema=Configuration)

# # Add the node to the graph
# workflow.add_node("my_node", my_node)

# # Set the entrypoint as `call_model`
# workflow.add_edge("__start__", "my_node")

# Compile the workflow into an executable graph
# graph_builder = StateGraph(State)

# graph_builder.add_node(chatbot)
# graph_builder.add_node(demo_get_precipitation_data_tool_validator)
# graph_builder.add_node(demo_get_precipitation_data_tool_runner)

# graph_builder.add_edge(START, "chatbot")
# graph_builder.add_conditional_edges("chatbot", chatbot_router)
# graph_builder.add_edge("demo_get_precipitation_data_tool_runner", "chatbot")

# memory = MemorySaver()

# graph = graph_builder.compile(checkpointer=memory)

# graph.name = "New Graph"  # This defines the custom name in LangSmith
