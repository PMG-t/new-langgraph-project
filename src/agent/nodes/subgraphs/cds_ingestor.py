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

cds_tools_dict = {
    cds_forecast_ingestor_tool.name: cds_forecast_ingestor_tool,
    cds_forecast_ingestor_tool_code_editor.name: cds_forecast_ingestor_tool_code_editor
}
cds_tool_names = list(cds_tools_dict.keys())
cds_tools = list(cds_tools_dict.values())

llm_with_cds_tools = utils._base_llm.bind_tools(cds_tools)



class StateCdsIngestor(State):
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
    
    if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
        next_node = CDS_INGESTOR_FORECAST_TOOL_HANDLER
    
    return next_node

# INFO: New-Way-GENERIC TOOL HANDLER [NODE]
def cds_forecast_tool_handler(state: StateCdsIngestor) -> Command[Literal[END, CDS_FORECAST_TOOL_INTERRUPT]]:   # type: ignore
    tool_message = state["messages"][-1]
    tool_call = tool_message.tool_calls[-1]
    
    result = None
    try:
        result = cds_tools_dict[tool_call['name']].invoke(tool_call['args'])
    except ToolInterrupt as tool_interrupt:
        update_state = {}
        update_state['nodes_params'] = { 
            CDS_FORECAST_TOOL_INTERRUPT: {
                'tool_message': tool_message,
                'tool_interrupt': tool_interrupt.as_dict,
                'tool_handler_node': CDS_INGESTOR_FORECAST_TOOL_HANDLER,    # INFO: Where to return interrupt "response" data
            }
        }
        return Command(goto=CDS_FORECAST_TOOL_INTERRUPT, update = update_state)     
            
    tool_response_message = utils.tool_response_message( 
        tool_call_id = tool_call['id'], 
        tool_name = tool_call['name'],
        tool_result = result
    )
    
    clean_state_update = { 'requested_agent': None, 'nodes_params': dict() }
    
    return {"messages": tool_response_message, **clean_state_update}

    

def cds_forecast_tool_interrupt(state: StateCdsIngestor) -> Command[Literal[END, CDS_INGESTOR_FORECAST_TOOL_HANDLER]]:   # type: ignore
    interrupt_data = state['nodes_params'][CDS_FORECAST_TOOL_INTERRUPT]
    tool_message = interrupt_data['tool_message']
    tool_interrupt = interrupt_data['tool_interrupt']
    tool_handler_node = interrupt_data['tool_handler_node']
    tool_name = interrupt_data['tool_interrupt']['tool']
    
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
            If the user provided some updates respond with a complete dictionary keyed with all the arguments they provided updated with what the user requested or provided as a value, if any.
            Reply with only the dictionary and nothing else.
            If the user asked to interrupt the tool process and exit, return None and nothing else.
            """,
            eval_output = True
        ) 
        if provided_args is not None:
            tool_message.tool_calls[-1]["args"].update(provided_args)
            cds_tools_dict[tool_name].extra_args['execution_confirmed'] = True
            return Command(goto = tool_handler_node, update = { "messages": [tool_message] })
    
    if tool_interrupt['type'] == ToolInterrupt.ToolInterruptType.CONFIRM_OUTPUT:
        output_description = '\n'.join([ f'- {out_name}: {out_value}' for out_name,out_value in tool_interrupt["data"]["output"].items() ])
        interrupt_message = utils.ask_llm(
            role = 'system',
            message = f"""Before the completion of the tool execution, some output needs to be confirmed. In particular:
            {tool_interrupt['reason']}
            Below there is the provided outputs:
            {output_description}
            Ask the user to confirm the output or if he want to modify some values."""
        )
        interruption = interrupt({
            "content": interrupt_message,
            "interrupt_type": ToolInterrupt.ToolInterruptType.CONFIRM_ARGS,
        })
        response = interruption.get('response', 'User did not provide any response.')
        provided_output = utils.ask_llm(
            role = 'system',
            message = f"""Before the completion of the tool execution, some output needs to be confirmed. In particular:
            {tool_interrupt['reason']}
            The user was asked to confirm if the output or if he want to modify some values.
            Below there is the provided outputs:
            {output_description}
            The user replied: "{response}".
            If the user provided some updates respond with a complete dictionary keyed with all the output they provided updated with what the user requested or provided as a value, if any.
            Reply with only the dictionary and nothing else.
            If the user asked to interrupt the tool process and exit, return None and nothing else.
            """,
            eval_output = True
        ) 
        if provided_output is not None:
            # TODO: We have to reconfirm if provided_output is different from output_description
            cds_tools_dict[tool_name].extra_args['output_confirmed'] = True
            cds_tools_dict[tool_name].extra_args['output'] = provided_output
            return Command(goto = tool_handler_node, update = { "messages": [tool_message] })
        
        
    # TODO: Remove tool message from state + add system exit message + goto END
    # return  Command(goto = CDS_CHATBOT, update = { "messages": [rem_tool, sys_exit] })
            
            
    
    
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