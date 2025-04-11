import os

from typing import Optional
from pydantic import BaseModel, Field
from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)

from agent import utils
from agent.names import *
from agent.tools import BaseAgentTool

import nbformat as nbf
from nbformat.v4 import new_code_cell



class CDSForecastIngestorCodeEditorTool(BaseAgentTool):
    
    class InputSchema(BaseModel):  # TODO: Better description
        
        source: None | str = Field(
            title = "Source",
            description = "The path to the code file to be edited. It could be a python notebbok, a script.py. If not specified use None as default.",
            examples = [
                None,
                'C:/path/to/python_script.py',
                'C:/path/to/python_notebook.ipynb'
            ],
            default=None
        )
        code_request: None | str | list[str] = Field(
            title="Request",
            description="""Meaning and usefulness of the requested code""",
            examples=[
                None,
                "Please add a function to plot the data.",
                "Please add a function to save the data in a different format.",
                [ "Please add a function to filter the data.", "Plot data by category" ]
            ]
        )
    
    
    def __init__(self, **kwargs):
        super().__init__(
            name = CDS_INGESTOR_FORECAST_CODE_EDITOR_TOOL,
            description = """Useful when user want to edit the code of a notebook regarding CDS forecast data ingestor tool.""",
            args_schema = CDSForecastIngestorCodeEditorTool.InputSchema,
            **kwargs
        )
    
    
    def _set_args_validation_rules(self):
        return {
            'source': [
                lambda **ka: f"Invalid source: {ka['source']}. It should be a valid path to a python script or jupyter notebook."
                    if not os.path.exists(ka['source']) else None
            ]
        }
        
    
    def _execute(
        self, 
        source: None | str,
        code_request: None | str | list[str],
    ):
        
        def get_source_code():
            if source.endswith('.ipynb'):
                nb = nbf.read(source, as_version=4)
                source_code = [cell.source for cell in nb.cells if cell.cell_type == 'code' and cell.source != '']
                source_code = '\n'.join(source_code)
            elif source.endswith('.py'):
                with open(source, 'r') as f:
                    source_code = f.read().split('\n')
            return source_code
        
        def add_source_code(source_code):
            if source.endswith('.ipynb'):
                nb = nbf.read(source, as_version=4)
                new_cell = new_code_cell(source = source_code)
                nb.cells.append(new_cell)
                nbf.write(nb, source)
            elif source.endswith('.py'):
                with open(source, 'a') as f:
                    f.write('\n')
                    f.write('# Code from ICisk AI Agent ----------------------------------------------------\n')
                    f.write(source_code)
                    f.write('\n')
                    f.write('-------------------------------------------------------------------------------\n')
                    
        if not self.output_confirmed:
            
            generated_code = utils.ask_llm(
                role = 'system',
                message = f"""
                    You are a programming assistant who helps users write python code.
                    Remember that the code is related to an analysis of geospatial data. If map visualizations are requested, use the cartopy library, adding borders, coastlines, lakes and rivers.

                    You have been asked to write python code that satisfies the following request:

                    {code_request}

                    The code produced must be added to this existing code:

                    {get_source_code()}

                    ------------------------------------------

                    Respond only with python code that can be integrated with the existing code. It must use the appropriate variables already defined in the code.
                    Do not attach any other text.
                    Do not produce additional code other than that necessary to satisfy the requests declared in the parameter.
                """,
                eval_output = False
            )
            
        else:
            generated_code = self.output['generated_code']
            add_source_code(generated_code)
                        
        return {
            "generated_code" : generated_code
        }
        
    
    
    # DOC: Try running AgentTool → Will check required, validity and inference over arguments thatn call and return _execute()
    def _run(
        self, 
        source: None | str,
        code_request: None | str | list[str],
        run_manager: None | Optional[CallbackManagerForToolRun] = None
    ) -> dict:
        
        self.execution_confirmed = True     # INFO: Skip this, there will be confirm-output-tool-exception
        
        return super()._run(
            tool_args = {
                "source": source,
                "code_request": code_request
            },
            run_manager=run_manager
        )