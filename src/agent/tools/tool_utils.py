from enum import Enum    
from typing import Optional
    
    
class ToolInterrupt(Exception):
    
    class ToolInterruptType(str, Enum):
        PROVIDE_ARGS = "PROVIDE_ARGS"
        INVALID_ARGS = "INVALID_ARGS"
        CONFIRM_ARGS = "CONFIRM_ARGS"
        CONFIRM_OUTPUT = "CONFIRM_OUTPUT"
        
    # child exception constructor
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