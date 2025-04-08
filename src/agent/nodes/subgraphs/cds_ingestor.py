import datetime

from typing_extensions import Literal

from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, RemoveMessage, HumanMessage

from langgraph.graph import MessagesState
from langgraph.graph import StateGraph
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt

from agent.names import *
from agent.states.state import State
from agent.tools import cds_temperature, cds_temperature_descriptors, CDSForecastIngestorTool, ToolInterrupt, CDSForecastIngestorCodeEditorTool
from agent import utils


# DOC: CDS-Ingestor subgraph - Exploit I-Cisk API to ingest CDS data. Data could be related to 'Temperature', 'Seasonal forecast', 'Glofas'

cds_forecast_ingestor_tool = CDSForecastIngestorTool()
cds_forecast_ingestor_tool_code_editor = CDSForecastIngestorCodeEditorTool()

cds_tools = [
    # cds_temperature,
    
    cds_forecast_ingestor_tool,
    cds_forecast_ingestor_tool_code_editor
]

llm_with_cds_tools = utils._base_llm.bind_tools(cds_tools)


class StateCdsIngestor(State):
    cds_ingestor_parameters: dict   # INFO: This is for keeping track of the parameters for the CDS ingestor tools. N.B. Keys are the same as the tool arguments
    nodes_params: dict  # INFO: This is for store some information that could be util for the nodes in the subgraph. N.B. Keys are node names, values are a custom dict
    



# INFO: CDS chatbot [NODE]
def cds_chatbot(state: StateCdsIngestor):    
    ai_message = llm_with_cds_tools.invoke(state["messages"])
    return {"messages": [ai_message]}


# INFO: CDS chatbot-router [NODE]
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
    
    if len(state.get('cds_ingestor_parameters', dict())) > 0 or (hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0):
        tool_calls = ai_message.tool_calls
        if len(state.get('cds_ingestor_parameters', dict())) > 0 or tool_calls[0]['name'] == CDS_INGESTOR_TEMPERATURE:
            next_node = CDS_INGESTOR_FORECAST_TOOL_HANDLER
    
        elif hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
            tool_call = ai_message.tool_calls[-1]
            if tool_call["name"] == CDS_INGESTOR_FORECAST_TOOL:
                print(CDS_INGESTOR_FORECAST_TOOL)
                next_node = CDS_INGESTOR_FORECAST_TOOL_HANDLER
            elif tool_call["name"] == CDS_INGESTOR_FORECAST_CODE_EDITOR_TOOL:
                print(CDS_INGESTOR_FORECAST_CODE_EDITOR_TOOL)
                next_node = CDS_INGESTOR_FORECAST_TOOL_HANDLER #CDS_INGESTOR_FORECAST_CODE_EDITOR_TOOL_HANDLER            
            
    print(f'\n\n\n NEXTNODE {next_node} \n\n\n')
    
    return next_node


# INFO: CDS Temperature tool handler [NODE]
# DOC: Requires user to specify region, init time, lead time, zarr out file
def cds_forecast_tool_handler(state: StateCdsIngestor) -> Command[Literal[CDS_INGESTOR_FORECAST_TOOL_RUNNER, CDS_FORECAST_TOOL_INTERRUPT]]:   # type: ignore
    # Run tool
    tool_message = state["messages"][-1]
    tool_call = tool_message.tool_calls[-1]
    
    print(f'\n\n\n TOOL CALL {tool_call} \n\n\n')
    
    tools = {
        CDS_INGESTOR_FORECAST_TOOL: cds_forecast_ingestor_tool,
        CDS_INGESTOR_FORECAST_CODE_EDITOR_TOOL: cds_forecast_ingestor_tool_code_editor, 
    }
    
    result = None
    tool_interrupt = None
    try:
        # result = cds_forecast_ingestor_tool.invoke(tool_call["args"])
        result = tools[tool_call['name']].invoke(tool_call['args'])
    except ToolInterrupt as tool_interrupt:
        # interrupt
        update_state = {}
        update_state['nodes_params'] = { 
            CDS_FORECAST_TOOL_INTERRUPT: {
                'tool_message': tool_message,
                'tool_interrupt': tool_interrupt.as_dict,
                'tool_handler_node': CDS_INGESTOR_FORECAST_TOOL_HANDLER,    # INFO: Where to return interrupt "response" data
            }
        }
        return Command(goto=CDS_FORECAST_TOOL_INTERRUPT, update = update_state)       
    
    
    print (f'\n\n\n TOOL message: {tool_message} \n\n\n')
    print(f'\n\n\n TOOL result: {result} \n\n\n')
    
            
    tool_response_message = {
        "role": "tool",
        "name": tool_call["name"],
        "content": result,
        "tool_call_id": tool_call["id"],
    }
    
    clean_state_update = { 
        'requested_agent': None,
        'nodes_params': dict(),
        'cds_ingestor_parameters': dict()
    }
    
    return {"messages": tool_response_message, **clean_state_update}
    

# !!!: To use this from different tool-handle you need to get handler-node and tool-var by messages
def cds_forecast_tool_interrupt(state: StateCdsIngestor) -> Command[Literal[END, CDS_INGESTOR_FORECAST_TOOL_HANDLER]]:   # type: ignore
    interrupt_data = state['nodes_params'][CDS_FORECAST_TOOL_INTERRUPT]
    tool_message = interrupt_data['tool_message']
    tool_interrupt = interrupt_data['tool_interrupt']
    tool_handler_node = interrupt_data['tool_handler_node']
    
    if tool_interrupt['type'] == ToolInterrupt.ToolInterruptType.PROVIDE_ARGS:
        args_description = '\n'.join([
            f'- {field} : {tool_interrupt["data"]["args_schema"][field].description}'
            for field in tool_interrupt['data']['args_schema'].keys()
            if field in tool_interrupt['data']['missing_args']
        ])        
        interrupt_message = utils.ask_llm(
            role = 'system',
            message = f"""The tool execution can't be completed for this reason:
            {tool_interrupt['reason']}
            Below there is a description of the required arguments:
            {args_description}
            Ask the user to provide the missing arguments for the tool execution."""
        )
        interruption = interrupt({
            "content": interrupt_message,
            "interrupt_type": ToolInterrupt.ToolInterruptType.PROVIDE_ARGS,
        })
        response = interruption.get('response', 'User did not provide any response.')
        provided_args = utils.ask_llm(
            role = 'system',
            message = f"""The tool execution could not be completed for this reason:
            {tool_interrupt['reason']}
            The user was asked to provide the missing arguments for the tool execution.
            The user replied: "{response}".
            If the user has provided valid arguments please reply with a dictionary with key the argument names and value what was specified by the user.
            If a value for an argument was not provided, then the value should be None.
            User can provide only some of the arguments.
            Reply with only the dictionary and nothing else.
            """,
            eval_output = True
        )        
        tool_message.tool_calls[-1]["args"].update(provided_args if provided_args is not None else dict())
        return Command(goto = tool_handler_node, update = { "messages": [tool_message] })        
    
    if tool_interrupt['type'] == ToolInterrupt.ToolInterruptType.INVALID_ARGS:
        args_description = '\n'.join([
            f"""- {field} : {tool_interrupt["data"]["args_schema"][field].description}
                    Invalid beacuse: {tool_interrupt["data"]["invalid_args"][field]}
            """
            for field in tool_interrupt['data']['args_schema'].keys()
            if field in tool_interrupt['data']['invalid_args']
        ])          
        interrupt_message = utils.ask_llm(
            role = 'system',
            message = f"""The tool execution can't be completed for this reason:
            {tool_interrupt['reason']}
            Below there is a description of the invalid arguments:
            {args_description}
            Ask the user to provide the valid arguments for the tool execution."""
        )
        interruption = interrupt({
            "content": interrupt_message,
            "interrupt_type": ToolInterrupt.ToolInterruptType.INVALID_ARGS,
        })
        response = interruption.get('response', 'User did not provide any response.')
        args_description = '\n'.join([ f'- {arg}: {val}' for arg,val in tool_message.tool_calls[-1]["args"].items() ])
        provided_args = utils.ask_llm(
            role = 'system',
            message = f"""The tool execution could not be completed for this reason:
            {tool_interrupt['reason']}
            Some of these arguments are invalid:
            {args_description}
            The user was asked to provide other valid arguments for the tool execution.
            The user replied: "{response}".
            If the user provided valid arguments, respond with a complete dictionary keyed with the all the arguments they provided updated with what the user provided as a value, if any.
            Reply with only the dictionary and nothing else.
            """,
            eval_output = True
        ) 
        tool_message.tool_calls[-1]["args"].update(provided_args)
        return Command(goto = tool_handler_node, update = { "messages": [tool_message] })
    
    if tool_interrupt['type'] == ToolInterrupt.ToolInterruptType.CONFIRM_ARGS:
        args_description = '\n'.join([ f'- {arg}: {val}' for arg,val in tool_interrupt["data"]["args"].items() ])
        interrupt_message = utils.ask_llm(
            role = 'system',
            message = f"""The tool execution can't be completed for this reason:
            {tool_interrupt['reason']}
            Below there is a description of the provided arguments:
            {args_description}
            Ask the user to confirm if the arguments are correct or if want to provide some updates."""
        )
        interruption = interrupt({
            "content": interrupt_message,
            "interrupt_type": ToolInterrupt.ToolInterruptType.CONFIRM_ARGS,
        })
        response = interruption.get('response', 'User did not provide any response.')
        provided_args = utils.ask_llm(
            role = 'system',
            message = f"""The tool execution could not be completed for this reason:
            {tool_interrupt['reason']}
            The user was asked to confirm if arguments are correct or if he wanted to provide some modification.
            Below there is a list with provided arguments and their values:
            {args_description}
            The user replied: "{response}".
            If the user provided some updates respond with a complete dictionary keyed with the all the arguments they provided updated with what the user requested or provided as a value, if any.
            Reply with only the dictionary and nothing else.
            If the user asked to interrupt the tool process and exit, return None and nothing else.
            """,
            eval_output = True
        ) 
        if provided_args is not None:
            tool_message.tool_calls[-1]["args"].update(provided_args)
            cds_forecast_ingestor_tool.extra_args['execution_confirmed'] = True # !!!: Not by tool-name
            return Command(goto = tool_handler_node, update = { "messages": [tool_message] })
    
    # TODO: Remove tool message from state + add system exit message + goto END
    # return  Command(goto = CDS_CHATBOT, update = { "messages": [rem_tool, sys_exit] })
            
            
# def cds_forecast_code_editor_tool_handler(state: StateCdsIngestor) -> Command[Literal[CDS_FORECAST_TOOL_INTERRUPT]]:   # type: ignore
#     # Run tool
#     tool_message = state["messages"][-1]
#     tool_call = tool_message.tool_calls[-1]
    
#     print(f'\n\n\n TOOL CALL {tool_call} \n\n\n')
    
#     result = None
#     tool_interrupt = None
#     try:
#         result = cds_forecast_ingestor_tool_code_editor.invoke(tool_call["args"])
#     except ToolInterrupt as tool_interrupt:
#         # interrupt
#         update_state = {}
#         update_state['nodes_params'] = { 
#             CDS_FORECAST_TOOL_INTERRUPT: {
#                 'tool_message': tool_message,
#                 'tool_interrupt': tool_interrupt.as_dict,
#                 'tool_handler_node': CDS_INGESTOR_FORECAST_CODE_EDITOR_TOOL_HANDLER,    # INFO: Where to return interrupt "response" data
#             }
#         }
#         return Command(goto=CDS_FORECAST_TOOL_INTERRUPT, update = update_state)       
    
    
#     print (f'\n\n\n TOOL message: {tool_message} \n\n\n')
#     print(f'\n\n\n TOOL result: {result} \n\n\n')
    
            
#     tool_response_message = {
#         "role": "tool",
#         "name": tool_call["name"],
#         "content": result,
#         "tool_call_id": tool_call["id"],
#     }
    
#     clean_state_update = { 
#         'requested_agent': None,
#         'nodes_params': dict(),
#         'cds_ingestor_parameters': dict()
#     }
    
#     return {"messages": tool_response_message, **clean_state_update}
 

# REGION: [OLD-CODE]

def cds_forecast_tool_handler_OLD(state: StateCdsIngestor) -> Command[Literal[CDS_INGESTOR_FORECAST_TOOL_HANDLE_REGION, CDS_INGESTOR_FORECAST_TOOL_HANDLE_INIT_TIME, CDS_INGESTOR_FORECAST_TOOL_HANDLE_LEAD_TIME, CDS_INGESTOR_FORECAST_TOOL_HANDLE_ZARR_OUTPUT_FILE, CDS_INGESTOR_FORECAST_TOOL_RUNNER, ]]:   # type: ignore    
    update_state = { 
        'messages': [], 
        'cds_ingestor_parameters': state.get('cds_ingestor_parameters', dict())
    }
    
    last_message = state["messages"][-1] 
    if hasattr(last_message, "tool_calls") and len(last_message.tool_calls) > 0:
        tool_call = last_message.tool_calls[-1]
        cds_ingestor_parameters = {
            'location': tool_call['args'].get('location', None),
            'init_time': tool_call['args'].get('init_time', None),
            'lead_time': tool_call['args'].get('lead_time', None),
            'zarr_output_file': tool_call['args'].get('zarr_output_file', None)
        }
        remove_tool_message = utils.remove_tool_messages(last_message)
        update_state['messages'].append(remove_tool_message)
        update_state['cds_ingestor_parameters'] = cds_ingestor_parameters
    
    if update_state['cds_ingestor_parameters'].get('location', None) is None:
        return Command(goto = CDS_INGESTOR_FORECAST_TOOL_HANDLE_REGION, update = update_state)
    if update_state['cds_ingestor_parameters'].get('init_time', None) is None:
        return Command(goto = CDS_INGESTOR_FORECAST_TOOL_HANDLE_INIT_TIME, update = update_state)
    if update_state['cds_ingestor_parameters'].get('lead_time', None) is None:
        return Command(goto = CDS_INGESTOR_FORECAST_TOOL_HANDLE_LEAD_TIME, update = update_state)
    if update_state['cds_ingestor_parameters'].get('zarr_output_file', None) is None:
        return Command(goto = CDS_INGESTOR_FORECAST_TOOL_HANDLE_ZARR_OUTPUT_FILE, update = update_state)

    tool_call_message = utils.build_tool_message(message_id=utils.guid(), tool_name=CDS_INGESTOR_TEMPERATURE, tool_args={
        "location": update_state['cds_ingestor_parameters']['location'],
        "init_time": update_state['cds_ingestor_parameters']['init_time'],
        "lead_time": update_state['cds_ingestor_parameters']['lead_time'],
        "zarr_output_file": update_state['cds_ingestor_parameters']['zarr_output_file']
    })
    update_state['messages'].append(tool_call_message)
    return Command(goto = CDS_INGESTOR_FORECAST_TOOL_RUNNER, update = update_state)


def tool_call_for_interrupt(update_state):
    return {
        "tool_calls": utils.build_tool_message(message_id=utils.guid(), tool_name=CDS_INGESTOR_TEMPERATURE, tool_args={
            "location": update_state['cds_ingestor_parameters'].get('location', None),
            "init_time": update_state['cds_ingestor_parameters'].get('init_time', None),
            "lead_time": update_state['cds_ingestor_parameters'].get('lead_time', None),
            "zarr_output_file": update_state['cds_ingestor_parameters'].get('zarr_output_file', None),
        }).tool_calls
    }

# INFO: CDS Temperature tool handle region [NODE] 
def cds_forecast_tool_handle_region(state: StateCdsIngestor) -> Command[Literal[END, CDS_INGESTOR_FORECAST_TOOL_HANDLER, CDS_INGESTOR_FORECAST_TOOL_HANDLE_REGION]]:   # type: ignore
    
    update_state = { 'messages': [], 'cds_ingestor_parameters': state.get('cds_ingestor_parameters', dict()), 'nodes_params': state.get('nodes_params', dict()) }
    
    provided_bbox = None
    
    user_response = interrupt({
        "content": utils.ask_llm(
            role = "system", 
            message = update_state['nodes_params'].get(CDS_INGESTOR_FORECAST_TOOL_HANDLE_REGION, dict()).get(
                'clarification_message', 
                """The user has requested the retrieval of temperature data.
                To do this, however, you need to provide a location.
                Ask the user to provide a location name or bounding box (min_lon, min_lat, max_lon, max_lat)."""
            )
        ),
        "response_key": "location",
        "interrupt_type": utils.InterruptType.CLARIFICATION,
        **tool_call_for_interrupt(update_state)
    })
    
    provided_bbox = utils.ask_llm(
        role = 'system',
        message = f"""The user was asked for which location he wanted to get the temperature data for.
        The user replied: "{user_response['location']}".
        If the user provided a bounding box then return it in the format [min_x, min_y, max_x, max_y] and nothing else.
        If the user entered a location then get and return the bounding box in the format [min_x, min_y, max_x, max_y].
        If the user did not provide a location then return None and nothing else.
        """,
        eval_output = True
    )
    
    if provided_bbox is None:
        
        invalid_response = user_response['location']
        
        is_exit_request = utils.ask_llm(
            role = 'system',
            message = f"""When asked to enter a location, the user responded with "{invalid_response}" and it was not possible to obtain a valid bounding box for it.
            Classifies whether the user response refers to a request to exit the tool execution or not.
            Returns True if the user wants to exit and close the tool execution, False otherwise.
            Do not return any other text.""",
            eval_output = True
        )
        if is_exit_request:
            update_state['messages'].append(SystemMessage(content = "The user has requested to exit the tool execution. Ask user if he want to restart or what you can do for him."))
            clean_state_update = { 
                'requested_agent': None,
                'nodes_params': dict(),
                'cds_ingestor_parameters': dict()
            }
            return Command(goto = CDS_CHATBOT, update = update_state | clean_state_update)
        else:
            clarification_message = utils.ask_llm(
                role = 'system',
                message = f""""When asked to enter a location for {CDS_INGESTOR_TEMPERATURE} tool, the user responded with "{invalid_response}". 
                Here is the description of the location argument: "{cds_temperature_descriptors['args']['location']}".
                He can also provide the name of a location if he don't know the bounding box.
                Based on user response choose if provide more information to user if he has requested or ask the user to try to specify the location of interest better or if he prefers to exit this tool.""",
                llm = llm_with_cds_tools,
                eval_output = False
            )
            update_state['nodes_params'] = { CDS_INGESTOR_FORECAST_TOOL_HANDLE_REGION: { 'clarification_message': clarification_message } }
            return Command(goto=CDS_INGESTOR_FORECAST_TOOL_HANDLE_REGION, update=update_state)
    
    else:
        tool_call_message = utils.build_tool_message(message_id=utils.guid(), tool_name=CDS_INGESTOR_TEMPERATURE, tool_args={
            "location": provided_bbox,
            "init_time": update_state['cds_ingestor_parameters'].get('init_time', None),
            "lead_time": update_state['cds_ingestor_parameters'].get('lead_time', None),
            "zarr_output_file": update_state['cds_ingestor_parameters'].get('zarr_output_file', None)
        })
        update_state['messages'].append(tool_call_message)
        return Command(goto = CDS_INGESTOR_FORECAST_TOOL_HANDLER, update = update_state)
    
    
def cds_forecast_tool_handle_init_time(state: StateCdsIngestor) -> Command[Literal[END, CDS_INGESTOR_FORECAST_TOOL_HANDLER, CDS_INGESTOR_FORECAST_TOOL_HANDLE_INIT_TIME]]:   # type: ignore
    
    update_state = { 'messages': [], 'cds_ingestor_parameters': state.get('cds_ingestor_parameters', dict()), 'nodes_params': state.get('nodes_params', dict()) }
    
    provided_init_month = None
    
    user_response = interrupt({
        "content": utils.ask_llm(
            role = "system", 
            message =  update_state['nodes_params'].get(CDS_INGESTOR_FORECAST_TOOL_HANDLE_INIT_TIME, dict()).get(
                'clarification_message', 
                """The user has requested the retrieval of temperature data.
                To do so, however, it is necessary to provide an init time (a year and a month) relative to the forecast.
                Ask the user for the date of the month in which the data is to be obtained"""
            )
        ),
        "response_key": "init_time",
        "interrupt_type": utils.InterruptType.CLARIFICATION,
        **tool_call_for_interrupt(update_state)
    })
    
    provided_init_month = utils.ask_llm(
        role = 'system',
        message = f"""The user was asked which month he wanted as the forecast initialization date.
        The user replied: "{user_response['init_time']}".
        Remeber that now the current year-month is {datetime.datetime.now().strftime('%Y-%m')}.
        If the user has provided a date with at least a month and a year then please provide it to me in 'YYYY-MM-dd' string format and nothing else.
        If the user did not provide a valid date then return None and nothing else.
        """,
        eval_output = True
    )
    
    if provided_init_month is None:
        
        invalid_response = user_response['init_time']
        
        is_exit_request = utils.ask_llm(
            role = 'system',
            message = f"""When asked to enter a init time for the forcast data, the user responded with "{invalid_response}" and it was not possible to obtain a valid date.
            Classifies whether the user response refers to a request to exit the tool execution or not.
            Returns True if the user wants to exit and close the tool execution, False otherwise.
            Do not return any other text.""",
            eval_output = True
        )
        if is_exit_request:
            update_state['messages'].append(SystemMessage(content = "The user has requested to exit the tool execution. Ask user if he want to restart or what you can do for him."))
            clean_state_update = { 
                'requested_agent': None,
                'nodes_params': dict(),
                'cds_ingestor_parameters': dict()
            }
            return Command(goto = CDS_CHATBOT, update = update_state | clean_state_update)
        else:
            clarification_message = utils.ask_llm(
                role = 'system',
                message = f""""When asked to enter a init time for {CDS_INGESTOR_TEMPERATURE} tool, the user responded with "{invalid_response}". 
                Here is the description of the init time argument: "{cds_temperature_descriptors['args']['init_time']}".
                Based on user response choose if provide more information to user if he has requested or ask the user to try to specify the init time better or if he prefers to exit this tool.""",
                llm = llm_with_cds_tools,
                eval_output = False
            )
            update_state['nodes_params'] = { CDS_INGESTOR_FORECAST_TOOL_HANDLE_INIT_TIME: { 'clarification_message': clarification_message } }
            return Command(goto=CDS_INGESTOR_FORECAST_TOOL_HANDLE_INIT_TIME, update=update_state)
        
    else:
        tool_call_message = utils.build_tool_message(message_id=utils.guid(), tool_name=CDS_INGESTOR_TEMPERATURE, tool_args={
            "location": update_state['cds_ingestor_parameters'].get('location', None),
            "init_time": datetime.datetime.strptime(provided_init_month, '%Y-%m-%d').date().isoformat(),
            "lead_time": update_state['cds_ingestor_parameters'].get('lead_time', None),
            "zarr_output_file": update_state['cds_ingestor_parameters'].get('zarr_output_file', None)
        })
        update_state['messages'].append(tool_call_message)
        return Command(goto = CDS_INGESTOR_FORECAST_TOOL_HANDLER, update = update_state)
    

def cds_forecast_tool_handle_lead_time(state: StateCdsIngestor) -> Command[Literal[END, CDS_INGESTOR_FORECAST_TOOL_HANDLER, CDS_INGESTOR_FORECAST_TOOL_HANDLE_LEAD_TIME]]:   # type: ignore
   
    update_state = { 'messages': [], 'cds_ingestor_parameters': state.get('cds_ingestor_parameters', dict()), 'nodes_params': state.get('nodes_params', dict()) }
    
    provided_lead_month = None
    
    user_response = interrupt({
        "content": utils.ask_llm(
            role = "system",
            message =  update_state['nodes_params'].get(CDS_INGESTOR_FORECAST_TOOL_HANDLE_LEAD_TIME, dict()).get(
                'clarification_message', 
                """The user has requested the retrieval of temperature data.
                To do so, however, it is necessary to provide a lead time relative to the forecast.
                Ask the user for the date of the month in which they want to obtain the data"""
            )
        ),
        "response_key": "lead_time",
        "interrupt_type": utils.InterruptType.CLARIFICATION,
        **tool_call_for_interrupt(update_state)
    })
    
    provided_lead_month = utils.ask_llm(
        role = 'system',
        message = f"""The user was asked up to what date he wanted to get the forecast data
        The user replied: "{user_response['lead_time']}".
        Remeber that now the current year-month is {datetime.datetime.now().strftime('%Y-%m')}.
        If the user has provided a date with at least a month and a year then please provide it to me in 'YYYY-MM-dd' string format and nothing else.
        If the user did not provide a valid date then return None and nothing else.
        """,
        eval_output = True
    )
    
    if provided_lead_month is None:
    
        invalid_response = user_response['lead_time']
        
        is_exit_request = utils.ask_llm(
            role = 'system',
            message = f"""When asked to enter a lead time for the forcast data, the user responded with "{invalid_response}" and it was not possible to obtain a valid date.
            Classifies whether the user response refers to a request to exit the tool execution or not.
            Returns True if the user wants to exit and close the tool execution, False otherwise.
            Do not return any other text.""",
            eval_output = True
        )
        if is_exit_request:
            update_state['messages'].append(SystemMessage(content = "The user has requested to exit the tool execution. Ask user if he want to restart or what you can do for him."))
            clean_state_update = { 
                'requested_agent': None,
                'nodes_params': dict(),
                'cds_ingestor_parameters': dict()
            }
            return Command(goto = CDS_CHATBOT, update = update_state | clean_state_update)
        else:
            clarification_message = utils.ask_llm(
                role = 'system',
                message = f""""When asked to enter a lead time for {CDS_INGESTOR_TEMPERATURE} tool, the user responded with "{invalid_response}". 
                Here is the description of the lead time argument: "{cds_temperature_descriptors['args']['lead_time']}".
                Based on user response choose if provide more information to user if he has requested or ask the user to try to specify the lead time better or if he prefers to exit this tool.""",
                llm = llm_with_cds_tools,
                eval_output = False
            )
            update_state['nodes_params'] = { CDS_INGESTOR_FORECAST_TOOL_HANDLE_LEAD_TIME: { 'clarification_message': clarification_message } }
            return Command(goto=CDS_INGESTOR_FORECAST_TOOL_HANDLE_LEAD_TIME, update=update_state)
    
    else:
        tool_call_message = utils.build_tool_message(message_id=utils.guid(), tool_name=CDS_INGESTOR_TEMPERATURE, tool_args={
            "location": update_state['cds_ingestor_parameters'].get('location', None),
            "init_time": update_state['cds_ingestor_parameters'].get('init_time', None),
            "lead_time": datetime.datetime.strptime(provided_lead_month, '%Y-%m-%d').date().isoformat(),
            "zarr_output_file": update_state['cds_ingestor_parameters'].get('zarr_output_file', None)
        })
        update_state['messages'].append(tool_call_message)
        return Command(goto = CDS_INGESTOR_FORECAST_TOOL_HANDLER, update = update_state)
    

def cds_forecast_tool_handle_zarr_output_file(state: StateCdsIngestor) -> Command[Literal[END, CDS_INGESTOR_FORECAST_TOOL_HANDLER, CDS_INGESTOR_FORECAST_TOOL_HANDLE_ZARR_OUTPUT_FILE]]:   # type: ignore
   
    update_state = { 'messages': [], 'cds_ingestor_parameters': state.get('cds_ingestor_parameters', dict()), 'nodes_params': state.get('nodes_params', dict()) }
    
    provided_zarr_output_file = None
    
    user_response = interrupt({
        "content": utils.ask_llm(
            role = "system",
            message =  update_state['nodes_params'].get(CDS_INGESTOR_FORECAST_TOOL_HANDLE_ZARR_OUTPUT_FILE, dict()).get(
                'clarification_message', 
                """The user requested to retrieve temperature data.
                To do this, however, you need to provide a name for the output file in zarr format.
                Ask the user to provide a file name or want a default name to be assigned."""
            )
        ),
        "response_key": "zarr_output_file",
        "interrupt_type": utils.InterruptType.CLARIFICATION,
        **tool_call_for_interrupt(update_state)
    })
    
    provided_zarr_output_file = utils.ask_llm(
        role = 'system',
        message = f"""The user was asked to provide a name for the zarr output file or to assign a default name.
        The user provided this response: '{user_response['zarr_output_file']}' .
        If he provided a valid file name, return it to me and nothing else.
        If it chooses to assign a default name, return 'default' and nothing else.
        Otherwise, return 'None' and nothing else.
        """,
        eval_output = True
    )
    
    if provided_zarr_output_file is None:
    
        invalid_response = user_response['zarr_output_file']
        
        is_exit_request = utils.ask_llm(
            role = 'system',
            message = f"""When asked to enter a zarr filename, the user responded with "{invalid_response}" and it was not possible to obtain a valid filename.
            Classifies whether the user response refers to a request to exit the tool execution or not.
            Returns True if the user wants to exit and close the tool execution, False otherwise.
            Do not return any other text.""",
            eval_output = True
        )
        if is_exit_request:
            update_state['messages'].append(SystemMessage(content = "The user has requested to exit the tool execution. Ask user if he want to restart or what you can do for him."))
            clean_state_update = { 
                'requested_agent': None,
                'nodes_params': dict(),
                'cds_ingestor_parameters': dict()
            }
            return Command(goto = CDS_CHATBOT, update = update_state | clean_state_update)
        else:
            clarification_message = utils.ask_llm(
                role = 'system',
                message = f""""When asked to enter a zarr filename for {CDS_INGESTOR_TEMPERATURE} tool, the user responded with "{invalid_response}". 
                Here is the description of the zarr filename argument: "{cds_temperature_descriptors['args']['zarr_output_file']}".
                Based on user response choose if provide more information to user if he has requested or ask the user to try to specify the filename better or if he prefers to exit this tool.""",
                llm = llm_with_cds_tools,
                eval_output = False
            )
            update_state['nodes_params'] = { CDS_INGESTOR_FORECAST_TOOL_HANDLE_ZARR_OUTPUT_FILE: { 'clarification_message': clarification_message } }
            return Command(goto=CDS_INGESTOR_FORECAST_TOOL_HANDLE_ZARR_OUTPUT_FILE, update=update_state)
    
    else:
        if provided_zarr_output_file == 'default':
            provided_zarr_output_file = f"temperature_{datetime.datetime.now().strftime('%Y-%m-%d')}.zarr"
        else:
            provided_zarr_output_file = f"{provided_zarr_output_file}.zarr" if not provided_zarr_output_file.endswith('.zarr') else provided_zarr_output_file
        tool_call_message = utils.build_tool_message(message_id=utils.guid(), tool_name=CDS_INGESTOR_TEMPERATURE, tool_args={
            "location": update_state['cds_ingestor_parameters'].get('location', None),
            "init_time": update_state['cds_ingestor_parameters'].get('init_time', None),
            "lead_time": update_state['cds_ingestor_parameters'].get('lead_time', None),
            "zarr_output_file": provided_zarr_output_file
        })
        update_state['messages'].append(tool_call_message)
        return Command(goto = CDS_INGESTOR_FORECAST_TOOL_HANDLER, update = update_state)


def cds_forecast_tool_runner_OLD(state: StateCdsIngestor):
    new_messages = []
    tools = {CDS_INGESTOR_TEMPERATURE: cds_temperature}
    tool_calls = state["messages"][-1].tool_calls
    for tool_call in tool_calls:
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
    
    # INFO: Tool is executed (parent graph state update)
    clean_state_update = { 
        'requested_agent': None,
        'nodes_params': dict(),
        'cds_ingestor_parameters': dict()
    }
    
    return {"messages": new_messages, **clean_state_update}

# ENDREGION: [OLD-CODE]    

def cds_forecast_tool_runner(state: StateCdsIngestor):
    new_messages = []
    tools = {CDS_INGESTOR_FORECAST_TOOL: cds_forecast_ingestor_tool}
    tool_calls = state["messages"][-1].tool_calls
    for tool_call in tool_calls:
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
        print(f"\n\n\n TOOL result: {result} \n\n\n")
    
    # INFO: Tool is executed (parent graph state update)
    clean_state_update = { 
        'requested_agent': None,
        'nodes_params': dict(),
        'cds_ingestor_parameters': dict()
    }
    
    return {"messages": new_messages, **clean_state_update}
    
    

cds_temperature_graph_builder = StateGraph(StateCdsIngestor)

cds_temperature_graph_builder.add_node(CDS_CHATBOT, cds_chatbot)
cds_temperature_graph_builder.add_node(CDS_INGESTOR_FORECAST_TOOL_HANDLER, cds_forecast_tool_handler)
# cds_temperature_graph_builder.add_node(CDS_INGESTOR_FORECAST_CODE_EDITOR_TOOL_HANDLER, cds_forecast_code_editor_tool_handler)
cds_temperature_graph_builder.add_node(CDS_FORECAST_TOOL_INTERRUPT, cds_forecast_tool_interrupt)
cds_temperature_graph_builder.add_node(CDS_INGESTOR_FORECAST_TOOL_HANDLE_REGION, cds_forecast_tool_handle_region)
cds_temperature_graph_builder.add_node(CDS_INGESTOR_FORECAST_TOOL_HANDLE_INIT_TIME, cds_forecast_tool_handle_init_time)
cds_temperature_graph_builder.add_node(CDS_INGESTOR_FORECAST_TOOL_HANDLE_LEAD_TIME, cds_forecast_tool_handle_lead_time)
cds_temperature_graph_builder.add_node(CDS_INGESTOR_FORECAST_TOOL_HANDLE_ZARR_OUTPUT_FILE, cds_forecast_tool_handle_zarr_output_file)
cds_temperature_graph_builder.add_node(CDS_INGESTOR_FORECAST_TOOL_RUNNER, cds_forecast_tool_runner)

cds_temperature_graph_builder.add_edge(START, CDS_CHATBOT)
cds_temperature_graph_builder.add_conditional_edges(CDS_CHATBOT, cds_chatbot_router)
cds_temperature_graph_builder.add_edge(CDS_INGESTOR_FORECAST_TOOL_RUNNER, CDS_CHATBOT)

cds_temperature_subgraph = cds_temperature_graph_builder.compile()
cds_temperature_subgraph.name = CDS_INGESTOR_FORECAST_SUBGRAPH