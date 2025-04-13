# DOC: Chatbot node and router

from typing_extensions import Literal

from langchain_core.messages import SystemMessage

from langgraph.graph import END
from langgraph.types import Command

from agent.names import *
from agent.states import State
from agent import utils


# DOC: chatbot node
def chatbot(state: State):
    state["messages"] = state.get("messages", [])
    
    last_message = state["messages"][-1] if 'messages' in state  and len(state['messages']) > 0 else None
    
    additional_messages = []
    state_updates = dict()
    
    if last_message is not None and utils.is_human_message(last_message):
        
        print('\n\n\n ??? \n\n\n')
        
        is_request_classified = False
        
        if not is_request_classified:
        
            is_help_request = utils.ask_llm(
                role = 'system',
                message = f"""You are a Multi-Agent AI. The user sent this message:
                "{last_message.content}"
                Classify whether this message is a request for an introduction or for information about what the agent (you) can do.
                Reply with True or False and nothing else.""",
                eval_output=True
            )    
            if is_help_request: 
                is_request_classified = True
                sys_message = SystemMessage(
                    content = f"""You are a MultiAgent AI built to help perform some climate data extraction tasks, leveraging some processes and APIs developed for I-CISK Project.
                    The user asked: "{last_message}".
                    Answer him by introducing yourself and explaining what you can do.
                    The tasks you can perform are the following:
                    - Help create a Jupyter notebook for the calculation of the SPI index on any geographic region, for a specified period of interest.
                    - Help to get and use temperature data from the CDS (Climate Data Store) via the ICisk APIs by building a jupyter notebook.
                    You do not have other tasks available at the moment, but your set of tasks will be expanded in the future."""
                )
                additional_messages.append(sys_message)
        
            agent_request = utils.ask_llm(
                role = 'system',
                message = f"""You are a multi-agent AI, and you are currently in a routing state following user input.
                Your task is to check which agent should be called based on the user input.

                The user message is as follows:
                "{last_message.content}"

                You have the following agents:
                - {CDS_FORECAST_SUBGRAPH}: This agent is responsible for helping to get climate data from the CDS (Climate Data Store) via Jupyter notebooks and generate or edit relatated python code.
                - {SPI_CALCULATION_SUBGRAPH}: This agent is responsible for helping to calculate the SPI (Standardized Precipitation Index) using the provided data and building a jupyter notebook for visualization.
            
                If the user request is related to a task that these agents can handle, respond with the name of the agent and nothing else.
                Otherwise, respond with 'None' and nothing else.
                """,
                eval_output = True
            )
            if agent_request is not None:
                if agent_request == CDS_FORECAST_SUBGRAPH:
                    is_request_classified = True
                    sys_message = f"""You are a MultiAgent AI built to help perform some climate data extraction tasks, leveraging some processes and APIs developed for I-CISK Project.
                        The user asked: "{last_message.content}".
                        The user's request can be fulfilled by the agent {agent_request}.
                        This agent is responsible for helping to get climate data from the CDS (Climate Data Store) via Jupyter notebooks and to edit relatated python code.
                        Let the user know that you will start the agent "CDS-FORECAST".
                        """
                    additional_messages.append(SystemMessage(content=sys_message))
                    state_updates["requested_agent"] = agent_request
                    
                elif agent_request == SPI_CALCULATION_SUBGRAPH:
                    is_request_classified = True
                    sys_message = f"""You are a MultiAgent AI built to help perform some climate data extraction tasks, leveraging some processes and APIs developed for I-CISK Project.
                        The user asked: "{last_message.content}".
                        The user's request can be fulfilled by the agent {agent_request}.
                        This agent is responsible for helping to calculate the SPI (Standardized Precipitation Index) using the provided data and building a jupyter notebook for visualization.
                        Let the user know that you will start the agent "SPI-CALCULATION".
                        """
                    additional_messages.append(SystemMessage(content=sys_message))
                    state_updates["requested_agent"] = agent_request
            
    if state_updates.get("requested_agent", None) is not None:
        state_updates["messages"] = [SystemMessage(content=f'The users made this request: "{last_message.content}". Run required tool if needed.')]
    else:
        ai_message = utils._llm_with_tools.invoke(state["messages"] + additional_messages)
        state_updates["messages"] = [ai_message]
    
    
    return state_updates


# DOC: chatbot router (conditional edge)
def chatbot_router(state: State) -> Literal[END, CDS_FORECAST_SUBGRAPH, SPI_CALCULATION_SUBGRAPH]: # type: ignore
    """
    Use in the conditional_edge to route to the ToolNode if the last message has tool calls. Otherwise, route to the end.
    """
    next_node = END
    
    if isinstance(state, list):
        last_message = state[-1]
    elif messages := state.get("messages", []):
        last_message = messages[-1]
        
    if state.get("requested_agent", None) is not None:
        if state["requested_agent"] == CDS_FORECAST_SUBGRAPH:
            next_node = CDS_FORECAST_SUBGRAPH
        elif state["requested_agent"] == SPI_CALCULATION_SUBGRAPH:
            next_node = SPI_CALCULATION_SUBGRAPH
            
    
    return next_node