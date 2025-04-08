import os
import re
import json
import datetime

from enum import Enum

from typing import Optional
from pydantic import BaseModel, Field

from langchain_core.tools import BaseTool
from langchain_core.tools.base import ArgsSchema
from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)

from agent.names import *
from agent import utils



# DOC: https://python.langchain.com/docs/how_to/custom_tools/#subclass-basetool
    

    
class ToolInterrupt(Exception):
    
    class ToolInterruptType(str, Enum):
        PROVIDE_ARGS = "PROVIDE_ARGS"
        INVALID_ARGS = "INVALID_ARGS"
        CONFIRM_ARGS = "CONFIRM_ARGS"
        
    # child exception constructor
    def __init__(self, interrupt_type: ToolInterruptType, interrupt_reason: str, interrupt_data: Optional[dict] = dict()):
        super().__init__(interrupt_reason)
        self.type = interrupt_type
        self.reason = interrupt_reason
        self.data = interrupt_data
    
    @property
    def message(self):
        return self.reason
    
    @property
    def as_dict(self):
        return {
            "type": self.type,
            "reason": self.reason,
            "data": self.data,
        }
    

class IPYNBCell():
    
    default_output = {
        "name": "stdout",
        "output_type": "stream",
        "text": []
    }
    
    def __init__(self, cell_type: str = 'code', source: str = '', execution_count: int = 1, metadata: dict = dict(), outputs: list = list()):
        self.cell_type = cell_type
        self.execution_count = execution_count
        self.metadata = metadata
        self.outputs = outputs if len(outputs) > 0 else [self.default_output]
        self.source = source
        
    def build_code(self, format_dict):
        lines = [line for line in self.source.split('\n')]
        while lines[0] == '':
            lines = lines[1:]
        while lines[-1] == '':
            lines = lines[:-1]
        spaces = re.match(r'^\s*', lines[0])
        spaces = len(spaces.group()) if spaces else 0
        lines = [line[spaces:] for line in lines]
        lines = [f'{line}\n' if idx!=len(lines)-1 else f'{line}' for idx,line in enumerate(lines)]
        lines = [line.format(**format_dict) for line in lines]
        return lines 
        
        
    def to_ipynb(self, format_dict: dict = dict()):
        return {
            "cell_type": self.cell_type,
            "execution_count": self.execution_count,
            "metadata": self.metadata,
            "outputs": self.outputs,
            "source": self.build_code(format_dict)
        }

class IPYNBSection():
    
    def __init__(self, title: str, description: str = None, cells: list[IPYNBCell] = list(), level: int=1):
        self.title = title
        self.description = description
        self.cells = cells
        self.level = level
        
    def to_ipynb(self, format_dict: dict = dict()):
        section_header_cell = IPYNBCell(
            cell_type = 'markdown',
            source = f"""
                {'#'*self.level} {self.title}
                {self.description if self.description else ''}
            """
        ) 
        code_cells = [ cell.to_ipynb(format_dict) for cell in self.cells ]
        return [ section_header_cell.to_ipynb() ] + code_cells

class IPYNBCoder():
    
    def __init__(self, notebook_path: str, sections: list[IPYNBSection], format_dict: dict = dict()):
        self.notebook_path = notebook_path
        self.sections = sections
        self.format_dict = format_dict
        
    def to_ipynb(self):
        ipynb_sections = [
            section.to_ipynb(self.format_dict)
            for section in self.sections
        ]
        ipynb_json = {
            "cells": [cell for section in ipynb_sections for cell in section],
            "metadata": dict(),
            "nbformat": 4,
            "nbformat_minor": 2
        }
        with open(self.notebook_path, 'w') as f:
            json.dump(ipynb_json, f)
        return self.notebook_path
    
    
class CDSForecastIngestorToolIPYNB(IPYNBCoder):
    
    sections = [
        IPYNBSection(
            title = "CDS Forecast Data Ingestor",
            description = "This notebook ingests forecast data from the Climate Data Store (CDS) API and saves it in a zarr format.",
        ),
        IPYNBSection(
            title = "Dependecies",
            cells = [
                IPYNBCell(
                    source = """
                        %%capture

                        import os
                        import json
                        import datetime
                        import requests
                        import getpass
                        import pprint

                        import xarray as xr

                        !pip install s3fs
                        import s3fs

                        !pip install "cdsapi>=0.7.4"
                        import cdsapi
                    """
                )
            ]
        ),
        IPYNBSection(
            title = "Parameters",
            cells = [
                IPYNBCell(
                    source = """
                    # Forcast variables
                    variables = {variables}
                    
                    # Bouning box of interest in format min_lon, min_lat, max_lon, max_lat
                    region = {area}

                    # init forecast time "YYYY-MM"
                    init_time = datetime.datetime.strptime({init_time}, "%Y-%m-%d").replace(day=1)

                    # lead forecast time "YYYY-MM"
                    lead_time = datetime.datetime.strptime({lead_time}, "%Y-%m-%d").replace(day=1)

                    # ingested data ouput zarr file
                    zarr_output = '{zarr_output}'
                    """
                )
            ]
        ),
        IPYNBSection(
            title = "ICISK API call",
            description = "This section exploits the I-CISK process _cds-ingestor_ to build data retrieval and storage.",
            cells = [
                IPYNBCell(
                    source = """
                        # Create payload for ICisk API
                    
                        icisk_api_payload = {{
                            "inputs": {{
                                "dataset": "seasonal-original-single-levels",
                                "file_out": f"/tmp/{{zarr_output.replace('.zarr', '')}}.netcdf",
                                "query": {{
                                    "originating_centre": "ecmwf",
                                    "system": "51",
                                    "variable": {variables},
                                    "year": [f"{{init_time.year}}"],
                                    "month": [f"{{init_time.month:02d}}"],
                                    "day": ["01"],
                                    "leadtime_hour": [str(h) for h in range(24, int(lead_time - init_time).total_seconds() // 3600, 24)],
                                    "area": [
                                        region[3],
                                        region[0],
                                        region[1],
                                        region[2]
                                    ],
                                    "data_format": "netcdf"
                                }},
                                "token": "YOUR-ICISK-API-TOKEN",
                                "zarr_out": f"s3://saferplaces.co/test/icisk/ai-agent/{{zarr_output}}",
                            }}
                        }}

                        print('-------------------------------------------------------------------------------')

                        pprint.pprint(icisk_api_payload)
                        
                        print('-------------------------------------------------------------------------------')
                        
                        # Request Token and run the process
                        
                        icisk_api_token = getpass.getpass("YOUR ICISK-API-TOKEN: ")

                        icisk_api_payload['inputs']['token'] = icisk_api_token

                        icisk_api_response = requests.post(
                            url = 'https://i-cisk.dev.52north.org/ingest/processes/ingestor-cds-process/execution',
                            json = icisk_api_payload
                        )
                        
                        print('-------------------------------------------------------------------------------')
                        
                        # Print the response
                        
                        pprint.pprint({{
                            'status_code': icisk_api_response.status_code, 
                            'response': icisk_api_response.json(),
                        }})
                        
                        print('-------------------------------------------------------------------------------')
                    """
                )
            ]
        )
    ]
     
    def __init__(self, notebook_path, args_dict: dict = dict()):
        super().__init__(notebook_path, self.sections, args_dict)   
        


class CDSForecastIngestorTool(BaseTool):

    class CDSForecastVariable(str, Enum):   # TODO: rename into 'CDSForecastIngestorVariable' 
    
        precipitation = "total-precipitation"
        temperature = "temperature"
        min_temperature = "minimum-temperature"
        max_temperature = "maximum-temperature"
        glofas = "glofas" # TODO: give a better name(s)
        
    class CDSForecastInput(BaseModel):  # TODO: rename into 'CDSForecastIngestorInput' 
        
        variables: None | list[str] = Field(
            title="Forecast-Variables",
            description="List of forecast variables to be retrieved from the CDS API. If not specified use None as default.",
            examples = [
                None,
                ['total-precipitation'],
                ['minimum-temperature', 'maximum-temperature'],
                ['total-precipitation', 'glofas'],
            ]
        )
        area: None | str | list[float] = Field(
            title="Area",
            description="""The area of interest for the forecast data. If not specified use None as default.
            It could be a bouning-box defined by [min_x, min_y, max_x, max_y] coordinates provided in EPSG:4326 Coordinate Reference System.
            Otherwise it can be the name of a country, continent, or specific geographic area.""",
            examples=[
                None,
                "Italy",
                "Paris",
                "Continental Spain",
                "Alps",
                [12, 52, 14, 53],
                [-5.5, 35.2, 5.58, 45.10],
            ]
        )
        init_time: None | str = Field(
            title="Initialization Time",
            description=f"The date of the forecast initialization provided in UTC-0 YYYY-MM-DD. If not specified use {datetime.datetime.now().strftime('%Y-%m-01')} as default.",
            examples=[
                None,
                "2025-01-01",
                "2025-02-01",
                "2025-03-10",
            ]
        )
        lead_time: None | str = Field(
            title="Lead Time",
            description=f"The end date of the forecast lead time provided in UTC-0 YYYY-MM-DD. If not specified use: {(datetime.datetime.now().date().replace(day=1) + datetime.timedelta(days=31)).strftime('%Y-%m-01')} as default.",
            examples=[
                None,
                "2023-02-01",
                "2023-03-01",
                "2023-04-10",
            ]
        )
        zarr_output: None | str = Field(
            title="Output Zarr File",
            description=f"The path to the output zarr file with the forecast data. In could be a local path or a remote path. If not specified is None", #'icisk-ai_cds-ingestor-output.zarr' as default.",
            examples=[
                None,
                "C:/Users/username/appdata/local/temp/output-variable.zarr",
                "/path/to/output-date-variable.zarr",
                "S3://bucket-name/path/to/varibale-date.zarr",
            ]
        )
        
    class CDSForecastIngestorToolIPYNB(IPYNBCoder):
    
        sections = [
            IPYNBSection(
                title = "CDS Forecast Data Ingestor",
                description = "This notebook ingests forecast data from the Climate Data Store (CDS) API and saves it in a zarr format.",
            ),
            IPYNBSection(
                title = "Dependecies",
                cells = [
                    IPYNBCell(
                        source = """
                            %%capture

                            import os
                            import json
                            import datetime
                            import requests
                            import getpass
                            import pprint

                            import xarray as xr

                            !pip install s3fs
                            import s3fs

                            !pip install "cdsapi>=0.7.4"
                            import cdsapi
                        """
                    )
                ]
            ),
            IPYNBSection(
                title = "Parameters",
                cells = [
                    IPYNBCell(
                        source = """
                        # Forcast variables
                        variables = {variables}
                        
                        # Bouning box of interest in format min_lon, min_lat, max_lon, max_lat
                        region = {area}

                        # init forecast time "YYYY-MM"
                        init_time = datetime.datetime.strptime({init_time}, "%Y-%m-%d").replace(day=1)

                        # lead forecast time "YYYY-MM"
                        lead_time = datetime.datetime.strptime({lead_time}, "%Y-%m-%d").replace(day=1)

                        # ingested data ouput zarr file
                        zarr_output = '{zarr_output}'
                        """
                    )
                ]
            ),
            IPYNBSection(
                title = "ICISK API call",
                description = "This section exploits the I-CISK process _cds-ingestor_ to build data retrieval and storage.",
                cells = [
                    IPYNBCell(
                        source = """
                            # Create payload for ICisk API
                        
                            icisk_api_payload = {{
                                "inputs": {{
                                    "dataset": "seasonal-original-single-levels",
                                    "file_out": f"/tmp/{{zarr_output.replace('.zarr', '')}}.netcdf",
                                    "query": {{
                                        "originating_centre": "ecmwf",
                                        "system": "51",
                                        "variable": {variables},
                                        "year": [f"{{init_time.year}}"],
                                        "month": [f"{{init_time.month:02d}}"],
                                        "day": ["01"],
                                        "leadtime_hour": [str(h) for h in range(24, int(lead_time - init_time).total_seconds() // 3600, 24)],
                                        "area": [
                                            region[3],
                                            region[0],
                                            region[1],
                                            region[2]
                                        ],
                                        "data_format": "netcdf"
                                    }},
                                    "token": "YOUR-ICISK-API-TOKEN",
                                    "zarr_out": f"s3://saferplaces.co/test/icisk/ai-agent/{{zarr_output}}",
                                }}
                            }}

                            print('-------------------------------------------------------------------------------')

                            pprint.pprint(icisk_api_payload)
                            
                            print('-------------------------------------------------------------------------------')
                            
                            # Request Token and run the process
                            
                            icisk_api_token = getpass.getpass("YOUR ICISK-API-TOKEN: ")

                            icisk_api_payload['inputs']['token'] = icisk_api_token

                            icisk_api_response = requests.post(
                                url = 'https://i-cisk.dev.52north.org/ingest/processes/ingestor-cds-process/execution',
                                json = icisk_api_payload
                            )
                            
                            print('-------------------------------------------------------------------------------')
                            
                            # Print the response
                            
                            pprint.pprint({{
                                'status_code': icisk_api_response.status_code, 
                                'response': icisk_api_response.json(),
                            }})
                            
                            print('-------------------------------------------------------------------------------')
                        """
                    )
                ]
            )
        ]
        
        
        def __init__(self, notebook_path, args_dict: dict = dict()):
            super().__init__(notebook_path, self.sections, args_dict)   

    
    name: str = CDS_INGESTOR_FORECAST_TOOL #"CDS-Forecast-Data-Ingestor"
    description: str = """"Useful when user want to forecast data from the Climate Data Store (CDS) API.
    This tool builds a jupityer notebook to ingests forecast data for a specific region and time period, and saves it in a zarr format.
    It exploits I-CISK APIs to build data retrieval and storage by leveraging these CDS dataset:
    - "Seasonal-Original-Single-Levels" for the seasonal forecast of temperature and precipitation data.
    - "CEMS Early Warning Data Store" for the river discharge forecasting (GloFAS) data.
    This tool returns the path to the output zarr file with the retireved forecast data and an editable jupyter notebook that was used to build the data ingest procedure.
    If not provided by the user, assign the specified default values to the arguments.
    """
    args_schema: Optional[ArgsSchema] = CDSForecastInput
    return_direct: bool = True
    
    extra_args: dict = dict()
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.extra_args = {
            'execution_confirmed': False,
        }
        
        
    def check_required_args(self, tool_args):
        missing_args = [arg for arg in list(self.args_schema.model_fields.keys()) if tool_args[arg] is None]
        
        if len(missing_args) > 0:
            self.extra_args['execution_confirmed'] = False
            raise ToolInterrupt(
                interrupt_type = ToolInterrupt.ToolInterruptType.PROVIDE_ARGS,
                interrupt_reason = f"Missing required arguments: {missing_args}.",
                interrupt_data = {
                    "missing_args": missing_args,
                    "args_schema": self.args_schema.model_fields
                }
            )
            
            
    def check_invalid_args(self, tool_args):
        invalid_args = dict()
        
        variables = tool_args.get('variables', None)
        area = tool_args.get('area', None)
        init_time = tool_args.get('init_time', None)
        lead_time = tool_args.get('lead_time', None)
        zarr_output = tool_args.get('zarr_output', None)
        
        if variables is not None:
            invalid_variables = []
            for variable in variables:
                try:
                    self.CDSForecastVariable(variable)
                except ValueError:
                    invalid_variables.append(variable)
            if len(invalid_variables) > 0:
                invalid_args['variables'] = f"Invalid variables: {invalid_variables}. It should be a list of valid CDS forecast variables: {[item.value for item in self.CDSForecastVariable]}."
                
        if area is not None:
            if isinstance(area, list) and len(area) != 4:
                invalid_args['area'] = f"Invalid area coordinates: {area}. It should be a list of 4 float values representing the bounding box [min_x, min_y, max_x, max_y]."
        
        if init_time is not None:
            try:
                datetime.datetime.strptime(init_time, '%Y-%m-%d')
                if datetime.datetime.strptime(init_time, '%Y-%m-%d') > datetime.datetime.now():
                    invalid_args['init_time'] =  f"Invalid initialization time: {init_time}. It should be in the past, at least in the previous month."
            except ValueError:
                invalid_args['init_time'] = f"Invalid initialization time: {init_time}. It should be in the format YYYY-MM-DD."
                
        if lead_time is not None:
            try:
                datetime.datetime.strptime(lead_time, '%Y-%m-%d')
            except ValueError:
                invalid_args['lead_time'] = f"Invalid lead time: {lead_time}. It should be in the format YYYY-MM-DD."
            try:
                if datetime.datetime.strptime(lead_time, '%Y-%m-%d') < datetime.datetime.strptime(init_time, '%Y-%m-%d'):
                    invalid_args['lead_time'] = f"Invalid lead time: {lead_time}. It should be greater than the initialization time: {init_time}."
            except ValueError:
                pass 
            
        if zarr_output is not None:
            if not zarr_output.endswith('.zarr'):
                invalid_args['zarr_output'] = f"Invalid output path: {zarr_output}. It should be a valid zarr file path."
                
        if len(invalid_args) > 0:
            self.extra_args['execution_confirmed'] = False
            raise ToolInterrupt(
                interrupt_type = ToolInterrupt.ToolInterruptType.INVALID_ARGS,
                interrupt_reason = f"Invalid arguments: {list(invalid_args.keys())}.",
                interrupt_data = {
                    "invalid_args": invalid_args,
                    "args_schema": self.args_schema.model_fields
                }
            )
            
    
    def infer_and_confirm_args(self, tool_args):
        variables = tool_args.get('variables', None)
        area = tool_args.get('area', None)
        init_time = tool_args.get('init_time', None)
        lead_time = tool_args.get('lead_time', None)
        zarr_output = tool_args.get('zarr_output', None)
        
        if type(area) is str:
            area = utils.ask_llm(
                role = 'system',
                message = f"Please provide the bounding box coordinates for the area: {area} with format [min_x, min_y, max_x, max_y] in EPSG:4326 Coordinate Reference System.",
                eval_output = True
            )
            self.extra_args['execution_confirmed'] = False
            
        if not self.extra_args['execution_confirmed']:
            raise ToolInterrupt(
                interrupt_type = ToolInterrupt.ToolInterruptType.CONFIRM_ARGS,
                interrupt_reason = "Please confirm the execution of the tool with the provided arguments.",
                interrupt_data = {
                    "args": {
                        "variables": variables,
                        "area": area,
                        "init_time": init_time,
                        "lead_time": lead_time,
                        "zarr_output": zarr_output,
                    },
                    "args_schema": self.args_schema.model_fields,
                }
            )
    

    def _run(
        self, 
        variables: None | list[CDSForecastVariable],
        area: None | str | list[float],
        init_time: None | str,
        lead_time: None | str,
        zarr_output: None | str,
        run_manager: None | Optional[CallbackManagerForToolRun] = None
    ) -> dict:
        
        def controls_before_execution():
            tool_args = {
                "variables": variables,
                "area": area,
                "init_time": init_time,
                "lead_time": lead_time,
                "zarr_output": zarr_output
            }
            self.check_required_args(tool_args)     # 1. Required arguments
            self.check_invalid_args(tool_args)      # 2. Invalid arguments
            self.infer_and_confirm_args(tool_args)  # 3. Infer and confirm arguments
            
        controls_before_execution()
        
        notebook_builder = CDSForecastIngestorToolIPYNB(
            notebook_path = os.path.join(utils._temp_dir, utils.justfname(utils.forceext(zarr_output, 'ipynb'))),
            args_dict = {
                "variables": variables,
                "area": area,
                "init_time": init_time,
                "lead_time": lead_time,
                "zarr_output": zarr_output
            }
        )
        notebook_path = notebook_builder.to_ipynb()    
        
        return {
            "data_source": zarr_output,
            "notebook": notebook_path,
        }
        
        
class CDSForecastIngestorCodeEditorTool(BaseTool):
    
    class InputSchema(BaseModel):  # TODO: Better description
        
        source: None | str = Field(
            title = "Source",
            description = "The code to be edited. It could be a python notebbok, a script.py. User can also provide some lines of python code. If not specified use None as default.",
            examples = [
                None,
                'C:/path/to/python_script.py',
                'C:/path/to/python_notebook.ipynb'
            ]
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
    
    
    name: str = CDS_INGESTOR_FORECAST_CODE_EDITOR_TOOL #'cds_ingestor_forecast_code_editor_tool' # CDS-Forecast-Data-Ingestor-Editor
    description: str = """Useful when user want to edit the code of a notebook regarding CDS forecast data ingestor tool."""
    args_schema: Optional[ArgsSchema] = InputSchema
    return_direct: bool = True
    
    extra_args: dict = dict()
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.extra_args = {
            'execution_confirmed': False,
        }
        
        
    def check_required_args(self, tool_args):
        missing_args = [arg for arg in list(self.args_schema.model_fields.keys()) if tool_args[arg] is None]
        
        if len(missing_args) > 0:
            self.extra_args['execution_confirmed'] = False
            raise ToolInterrupt(
                interrupt_type = ToolInterrupt.ToolInterruptType.PROVIDE_ARGS,
                interrupt_reason = f"Missing required arguments: {missing_args}.",
                interrupt_data = {
                    "missing_args": missing_args,
                    "args_schema": self.args_schema.model_fields
                }
            )
            
        
    def check_invalid_args(self, tool_args):
        invalid_args = dict()
        
        source = tool_args.get('source', None)
        code_request = tool_args.get('code_request', None)
        
        if source is not None:
            if not os.path.exists(source):
                invalid_args['source'] = f"Invalid source: {source}. It should be a valid path to a python script or jupyter notebook."
            
        if len(invalid_args) > 0:
            self.extra_args['execution_confirmed'] = False
            raise ToolInterrupt(
                interrupt_type = ToolInterrupt.ToolInterruptType.INVALID_ARGS,
                interrupt_reason = f"Invalid arguments: {list(invalid_args.keys())}.",
                interrupt_data = {
                    "invalid_args": invalid_args,
                    "args_schema": self.args_schema.model_fields
                }
            )
        
    
    def infer_and_confirm_args(self, tool_args):
        source = tool_args.get('source', None)
        code_request = tool_args.get('code_request', None)
        
        # TODO: Here some inference on data transformation (not by now)
        
        if not self.extra_args['execution_confirmed']:
            self.extra_args['execution_confirmed'] = True # !!!: remove
            raise ToolInterrupt(
                interrupt_type = ToolInterrupt.ToolInterruptType.CONFIRM_ARGS,
                interrupt_reason = "Please confirm the execution of the tool with the provided arguments.",
                interrupt_data = {
                    "args": {
                        "source": source,
                        "code_request": code_request
                    },
                    "args_schema": self.args_schema.model_fields,
                }
            )
            
    def output_confirm(self, tool_args, tool_output):
        return None # TODO: this for preview the code before execution (writing)
    
    
    def _run(
        self, 
        source: None | str,
        code_request: None | str | list[str],
        run_manager: None | Optional[CallbackManagerForToolRun] = None
    ) -> dict:
        
        def controls_before_execution():
            tool_args = {
                "source": source,
                "code_request": code_request
            }
            self.check_required_args(tool_args)     # 1. Required arguments
            self.check_invalid_args(tool_args)      # 2. Invalid arguments
            self.infer_and_confirm_args(tool_args)  # 3. Infer and confirm arguments
            
        controls_before_execution()
        
        return {
            "generated_code" : [
                """
                import matplotlib.pyplot as plt
                
                plt.figure(figsize=(10, 6))
                plt.plot(data['time'], data['precipitation'], label='Precipitation')
                plt.plot(data['time'], data['temperature'], label='Temperature')
                plt.xlabel('Time')
                plt.ylabel('Value')
                plt.title('Weather Data')
                plt.legend()
                plt.show()
                """
            ]
        }