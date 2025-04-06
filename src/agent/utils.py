# DOC: Generic utils

import os
import ast
import uuid
import tempfile

from langchain_openai import ChatOpenAI

from langchain_core.messages import RemoveMessage, AIMessage

from agent.tools import demo_get_precipitation_data
from agent.tools import spi_notebook_creation, spi_notebook_editor




# REGION: [Generic utils]

_temp_dir = os.path.join(tempfile.gettempdir(), 'icisk-chat')
os.makedirs(_temp_dir, exist_ok=True)

def guid():
    return str(uuid.uuid4())

# ENDREGION: [Generic utils]



# REGION: [LLM and Tools]

_tools = [
    # demo_get_precipitation_data,      # INFO: demo tool
    
    spi_notebook_creation,            # INFO: spi tool
    spi_notebook_editor,              # INFO: spi tool
]

_base_llm = ChatOpenAI(model="gpt-4o-mini")
_llm_with_tools = _base_llm.bind_tools(_tools)

def ask_llm(role, message, llm=_base_llm, eval_output=False):
    llm_out = llm.invoke([{"role": role, "content": message}])
    if eval_output:
        try: return ast.literal_eval(llm_out.content)
        except: pass
    return llm_out.content

# ENDREGION: [LLM and Tools]



# REGION: [Message utils funtion]

class InterruptType:
    CLARIFICATION = "clarification"
    CONFIRMATION = "confirmation"

def is_human_message(message):
    return message.type == 'human'

def last_human_message(state):
    if 'messages' in state and len(state['messages'])    > 0:
        recent_messages = state['messages'][::-1]
        for message in recent_messages:
            if is_human_message(message):
                return message
    return None

def remove_message(message_id):
    return RemoveMessage(id = message_id)

def remove_tool_messages(tool_messages):
    if type(tool_messages) is not list:
        return remove_message(tool_messages.id)
    else:
        return [remove_message(tm.id) for tm in tool_messages]
    
def build_tool_message(message_id, tool_name, tool_args):
    tool_message = AIMessage(
        content = '',
        tool_calls = [
            {
                "id": message_id,
                "name": tool_name,
                "args": { arg_name: arg_value for arg_name, arg_value in tool_args.items() }
            }
        ]
    )
    return tool_message
    
# ENDREGION: [Message utils funtion]
    