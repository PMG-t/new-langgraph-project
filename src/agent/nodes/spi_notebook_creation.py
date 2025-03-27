# DOC: Demo get precipitation data node

from typing_extensions import Literal
from langgraph.types import Command
from langchain_core.messages import RemoveMessage

from geopy.geocoders import Nominatim

from ..names import *
from ..states import State
from ..tools import spi_notebook_creation


def get_bounding_box(location_name):
    geolocator = Nominatim(user_agent="bounding_box_finder")
    location = geolocator.geocode(location_name, exactly_one=True)

    if location and hasattr(location, 'raw'):
        bounding_box = location.raw.get('boundingbox', None)
        if bounding_box:
            min_lat, max_lat, min_lon, max_lon = map(float, bounding_box)
            return [min_lon, min_lat, max_lon, max_lat]
    
    return None


def spi_notebook_creation_tool_validator(state: State) -> Command[Literal[CHATBOT, SPI_NOTEBOOK_CREATION_TOOL_RUNNER]]: # type: ignore
    tool_message = state["messages"][-1]
    tool_call = tool_message.tool_calls[-1]
    
    is_region_specified = 'region' in tool_call['args'] and tool_call['args']['region'] not in [None, ""]
    is_reference_period_specified = 'reference_period' in tool_call['args'] and tool_call['args']['reference_period'] not in [None, ""]
    is_period_of_interest_specified = 'period_of_interest' in tool_call['args'] and tool_call['args']['period_of_interest'] not in [None, ""]
    
    if is_region_specified and is_reference_period_specified and is_period_of_interest_specified:
        
        if type(tool_call['args']['region']) is str:
            rem_msg = [RemoveMessage(id=tool_message.id)]
            region_name = tool_call['args']['region']
            bounding_box = get_bounding_box(region_name)
            if bounding_box is not None:
                tool_call['args']['region'] = bounding_box
                sys_message = f"""
                    L'utente a rihiesto di eseguire il tool {tool_call["name"]} con  questi argomenti:
                    - region: {tool_call['args']['region']}
                    - reference_period: {tool_call['args']['reference_period']}
                    - period_of_interest: {tool_call['args']['period_of_interest']}
                    Per l'argomento region è stata ricavata questa bounding box: {tool_call['args']['region']}. Chiedi all'utente se è corretta oppure se vuole modificarla.
                """
                feedback_message = {"role": "system", "content": sys_message}
                return Command(goto=CHATBOT, update={"messages": rem_msg + [feedback_message]})
            else:
                sys_message = f"""
                    L'utente a rihiesto di eseguire il tool {tool_call["name"]} con  questi argomenti:
                    - region: {tool_call['args']['region']}
                    - reference_period: {tool_call['args']['reference_period']}
                    - period_of_interest: {tool_call['args']['period_of_interest']}
                    Per l'argomento region non è stato possibile ricavare una bounding box. Chiedi all'utente di inserire manualmente i valori in formato [min_lon, min_lat, max_lon, max_lat]
                """
                feedback_message = {"role": "system", "content": sys_message}
                return Command(goto=CHATBOT, update={"messages": rem_msg + [feedback_message]})
        else:
            # TODO: Implement a confirmation request
            return Command(goto=SPI_NOTEBOOK_CREATION_TOOL_RUNNER)
    
    elif not is_region_specified:
        rem_msg = [RemoveMessage(id=tool_message.id)]
        sys_message = f"""
            L\'utente a rihiesto di eseguire il tool {tool_call["name"]} con  questi argomenti:
            - region: NULL
            - period_of_interest: {tool_call['args']['reference_period'] if is_reference_period_specified else "NULL"}
            - period_of_interest: {tool_call['args']['period_of_interest'] if is_period_of_interest_specified else "NULL"}
            Non ha specificato la region. Chiedigliela.
        """
        feedback_message = {"role": "system", "content": sys_message}
        return Command(goto=CHATBOT, update={"messages": rem_msg + [feedback_message]})
    
    elif not is_reference_period_specified:
        rem_msg = [RemoveMessage(id=tool_message.id)]
        sys_message = f"""
            L\'utente a rihiesto di eseguire il tool {tool_call["name"]} con  questi argomenti:
            - region: {tool_call['args']['region'] if is_region_specified else "NULL"}
            - reference_period: NULL
            - period_of_interest: {tool_call['args']['period_of_interest'] if is_period_of_interest_specified else "NULL"}
            Non ha specificato il periodo di riferimento. Chiedigli se vuole usare l'intervallo 1980-2010 di deafult oppure preferisce specificarlo.
        """
        feedback_message = {"role": "system", "content": sys_message}
        return Command(goto=CHATBOT, update={"messages": rem_msg + [feedback_message]})
    
    elif not is_period_of_interest_specified:
        rem_msg = [RemoveMessage(id=tool_message.id)]
        sys_message = f"""
            L\'utente a rihiesto di eseguire il tool {tool_call["name"]} con  questi argomenti:
            - region: {tool_call['args']['region'] if is_region_specified else "NULL"}
            - reference_period: {tool_call['args']['reference_period'] if is_reference_period_specified else "NULL"}
            - period_of_interest: NULL
            Non ha specificato il periodo di interesse. Chiedigli se vuole usare l'intervallo di default (il mese precedente alla data corrente) oppure preferisce specificarlo.
        """
        feedback_message = {"role": "system", "content": sys_message}
        return Command(goto=CHATBOT, update={"messages": rem_msg + [feedback_message]})
    
    else:
        print('Non OK!')
        rem_msg = [RemoveMessage(id=tool_message.id)]
        return Command(goto=CHATBOT, update={"messages": rem_msg + [feedback_message]})
 


def spi_notebook_creation_tool_runner(state):
    new_messages = []
    tools = {SPI_NOTEBOOK_CREATION: spi_notebook_creation}
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