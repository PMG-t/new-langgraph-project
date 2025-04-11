from enum import Enum    

import types
from typing import Optional
from typing_extensions import Literal

from langgraph.graph import END
from langgraph.types import Command, interrupt
from langchain_core.messages import SystemMessage

from agent import utils
    

# DOC: ToolInterrupt is a custom exception class that is used to handle interruptions in the tool execution process.
    
class ToolInterrupt(Exception):
    
    
    # DOC: ToolInterruptType is an enumeration that defines the types of interruptions that can occur during tool execution.
    class ToolInterruptType(str, Enum):
        PROVIDE_ARGS = "PROVIDE_ARGS"
        INVALID_ARGS = "INVALID_ARGS"
        CONFIRM_ARGS = "CONFIRM_ARGS"
        CONFIRM_OUTPUT = "CONFIRM_OUTPUT"
        
    # DOC: When an instance of ToolInterrupt is created, it needs the caller Tool object, interrupt-type, interrupt-reason and optional interrupt-data based on interrupt-type
    def __init__(self, interrupt_tool: str, interrupt_type: ToolInterruptType, interrupt_reason: str, interrupt_data: Optional[dict] = dict()):
        super().__init__(interrupt_reason)
        self.tool = interrupt_tool
        self.type = interrupt_type
        self.reason = interrupt_reason
        self.data = interrupt_data
    
    @property
    def message(self):
        return self.reason
    
    @property
    def as_dict(self):
        return {
            "tool": self.tool,
            "type": self.type,
            "reason": self.reason,
            "data": self.data,
        }