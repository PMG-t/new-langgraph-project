# DOC: Generic utils

import os
import tempfile

from langchain_openai import ChatOpenAI

from agent.tools import demo_get_precipitation_data, spi_notebook_creation, spi_notebook_editor



_temp_dir = os.path.join(tempfile.gettempdir(), 'icisk-chat')
os.makedirs(_temp_dir, exist_ok=True)





_tools = [
    demo_get_precipitation_data,      # INFO: demo tool
    
    spi_notebook_creation,            # INFO: spi tool
    spi_notebook_editor,              # INFO: spi tool
]

_llm = ChatOpenAI(model="gpt-4o-mini")
_llm_with_tools = _llm.bind_tools(_tools)