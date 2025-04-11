import os
import re
import json
import datetime
from enum import Enum

import nbformat as nbf
from nbformat.v4 import new_code_cell

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
from agent.tools.tool_interrupt import ToolInterrupt



# DOC: https://python.langchain.com/docs/how_to/custom_tools/#subclass-basetool


# class CDSForecastIngestorTool(BaseTool):

#     class CDSForecastVariable(str, Enum):   # TODO: rename into 'CDSForecastIngestorVariable' 
    
#         precipitation = "total-precipitation"
#         temperature = "temperature"
#         min_temperature = "minimum-temperature"
#         max_temperature = "maximum-temperature"
#         glofas = "glofas" # TODO: give a better name(s)
        
#         @property
#         def as_cds(self) -> str:
#             return {
#                 'total-precipitation': 'total_precipitation',
#                 'temperature': '2m_temperature',
#             }.get(self.value)
            
#         @property
#         def as_icisk(self) -> str:
#             return {
#                 'total-precipitation': 'tp',
#                 'temperature': 't2m',
#             }.get(self.value)
        
#     class CDSForecastInput(BaseModel):  # TODO: rename into 'CDSForecastIngestorInput' 
        
#         variables: None | list[str] = Field(
#             title="Forecast-Variables",
#             description="List of forecast variables to be retrieved from the CDS API. If not specified use None as default.",
#             examples = [
#                 None,
#                 ['total-precipitation'],
#                 ['minimum-temperature', 'maximum-temperature'],
#                 ['total-precipitation', 'glofas'],
#             ]
#         )
#         area: None | str | list[float] = Field(
#             title="Area",
#             description="""The area of interest for the forecast data. If not specified use None as default.
#             It could be a bouning-box defined by [min_x, min_y, max_x, max_y] coordinates provided in EPSG:4326 Coordinate Reference System.
#             Otherwise it can be the name of a country, continent, or specific geographic area.""",
#             examples=[
#                 None,
#                 "Italy",
#                 "Paris",
#                 "Continental Spain",
#                 "Alps",
#                 [12, 52, 14, 53],
#                 [-5.5, 35.2, 5.58, 45.10],
#             ]
#         )
#         init_time: None | str = Field(
#             title="Initialization Time",
#             description=f"The date of the forecast initialization provided in UTC-0 YYYY-MM-DD. If not specified use {datetime.datetime.now().strftime('%Y-%m-01')} as default.",
#             examples=[
#                 None,
#                 "2025-01-01",
#                 "2025-02-01",
#                 "2025-03-10",
#             ]
#         )
#         lead_time: None | str = Field(
#             title="Lead Time",
#             description=f"The end date of the forecast lead time provided in UTC-0 YYYY-MM-DD. If not specified use: {(datetime.datetime.now().date().replace(day=1) + datetime.timedelta(days=31)).strftime('%Y-%m-01')} as default.",
#             examples=[
#                 None,
#                 "2023-02-01",
#                 "2023-03-01",
#                 "2023-04-10",
#             ]
#         )
#         zarr_output: None | str = Field(
#             title="Output Zarr File",
#             description=f"The path to the output zarr file with the forecast data. In could be a local path or a remote path. If not specified is None", #'icisk-ai_cds-ingestor-output.zarr' as default.",
#             examples=[
#                 None,
#                 "C:/Users/username/appdata/local/temp/output-variable.zarr",
#                 "/path/to/output-date-variable.zarr",
#                 "S3://bucket-name/path/to/varibale-date.zarr",
#             ]
#         )
        
    
#     name: str = CDS_INGESTOR_FORECAST_TOOL #"CDS-Forecast-Data-Ingestor"
#     description: str = """"Useful when user want to forecast data from the Climate Data Store (CDS) API.
#     This tool builds a jupityer notebook to ingests forecast data for a specific region and time period, and saves it in a zarr format.
#     It exploits I-CISK APIs to build data retrieval and storage by leveraging these CDS dataset:
#     - "Seasonal-Original-Single-Levels" for the seasonal forecast of temperature and precipitation data.
#     - "CEMS Early Warning Data Store" for the river discharge forecasting (GloFAS) data.
#     This tool returns the path to the output zarr file with the retireved forecast data and an editable jupyter notebook that was used to build the data ingest procedure.
#     If not provided by the user, assign the specified default values to the arguments.
#     """
#     args_schema: Optional[ArgsSchema] = CDSForecastInput
#     return_direct: bool = True
    
#     extra_args: dict = dict()
    
#     notebook: nbf.NotebookNode = nbf.v4.new_notebook()
    
    
#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)
#         self.extra_args = {
#             'execution_confirmed': False,
#         }
        
        
#     def check_required_args(self, tool_args):
#         missing_args = [arg for arg in list(self.args_schema.model_fields.keys()) if tool_args[arg] is None]
        
#         if len(missing_args) > 0:
#             self.extra_args['execution_confirmed'] = False
#             raise ToolInterrupt(
#                 interrupt_tool = self.name,
#                 interrupt_type = ToolInterrupt.ToolInterruptType.PROVIDE_ARGS,
#                 interrupt_reason = f"Missing required arguments: {missing_args}.",
#                 interrupt_data = {
#                     "missing_args": missing_args,
#                     "args_schema": self.args_schema.model_fields
#                 }
#             )
            
            
#     def check_invalid_args(self, tool_args):
#         invalid_args = dict()
        
#         variables = tool_args.get('variables', None)
#         area = tool_args.get('area', None)
#         init_time = tool_args.get('init_time', None)
#         lead_time = tool_args.get('lead_time', None)
#         zarr_output = tool_args.get('zarr_output', None)
        
#         if variables is not None:
#             invalid_variables = []
#             if len(variables) > 1:
#                 invalid_args['variables'] = f"Invalid variables: {variables}. By now only one variable is supported."
#             else:
#                 for variable in variables:
#                     try:
#                         self.CDSForecastVariable(variable)
#                     except ValueError:
#                         invalid_variables.append(variable)
#                 if len(invalid_variables) > 0:
#                     invalid_args['variables'] = f"Invalid variables: {invalid_variables}. It should be a list of valid CDS forecast variables: {[item.value for item in self.CDSForecastVariable]}."
                
#         if area is not None:
#             if isinstance(area, list) and len(area) != 4:
#                 invalid_args['area'] = f"Invalid area coordinates: {area}. It should be a list of 4 float values representing the bounding box [min_x, min_y, max_x, max_y]."
        
#         if init_time is not None:
#             try:
#                 datetime.datetime.strptime(init_time, '%Y-%m-%d')
#                 if datetime.datetime.strptime(init_time, '%Y-%m-%d') > datetime.datetime.now():
#                     invalid_args['init_time'] =  f"Invalid initialization time: {init_time}. It should be in the past, at least in the previous month."
#             except ValueError:
#                 invalid_args['init_time'] = f"Invalid initialization time: {init_time}. It should be in the format YYYY-MM-DD."
                
#         if lead_time is not None:
#             try:
#                 datetime.datetime.strptime(lead_time, '%Y-%m-%d')
#             except ValueError:
#                 invalid_args['lead_time'] = f"Invalid lead time: {lead_time}. It should be in the format YYYY-MM-DD."
#             try:
#                 if datetime.datetime.strptime(lead_time, '%Y-%m-%d') < datetime.datetime.strptime(init_time, '%Y-%m-%d'):
#                     invalid_args['lead_time'] = f"Invalid lead time: {lead_time}. It should be greater than the initialization time: {init_time}."
#             except ValueError:
#                 pass 
            
#         if zarr_output is not None:
#             if not zarr_output.endswith('.zarr'):
#                 invalid_args['zarr_output'] = f"Invalid output path: {zarr_output}. It should be a valid zarr file path."
                
#         if len(invalid_args) > 0:
#             self.extra_args['execution_confirmed'] = False
#             raise ToolInterrupt(
#                 interrupt_tool = self.name,
#                 interrupt_type = ToolInterrupt.ToolInterruptType.INVALID_ARGS,
#                 interrupt_reason = f"Invalid arguments: {list(invalid_args.keys())}.",
#                 interrupt_data = {
#                     "invalid_args": invalid_args,
#                     "args_schema": self.args_schema.model_fields
#                 }
#             )
            
    
#     def infer_and_confirm_args(self, tool_args):
#         variables = tool_args.get('variables', None)
#         area = tool_args.get('area', None)
#         init_time = tool_args.get('init_time', None)
#         lead_time = tool_args.get('lead_time', None)
#         zarr_output = tool_args.get('zarr_output', None)
        
#         if type(area) is str:
#             area = utils.ask_llm(
#                 role = 'system',
#                 message = f"Please provide the bounding box coordinates for the area: {area} with format [min_x, min_y, max_x, max_y] in EPSG:4326 Coordinate Reference System.",
#                 eval_output = True
#             )
#             self.extra_args['execution_confirmed'] = False
            
#         if not self.extra_args['execution_confirmed']:
#             raise ToolInterrupt(
#                 interrupt_tool = self.name,
#                 interrupt_type = ToolInterrupt.ToolInterruptType.CONFIRM_ARGS,
#                 interrupt_reason = "Please confirm the execution of the tool with the provided arguments.",
#                 interrupt_data = {
#                     "args": {
#                         "variables": variables,
#                         "area": area,
#                         "init_time": init_time,
#                         "lead_time": lead_time,
#                         "zarr_output": zarr_output,
#                     },
#                     "args_schema": self.args_schema.model_fields,
#                 }
#             )
    
#     def create_notebook(self):
#         self.notebook.cells = [
#             nbf.v4.new_code_cell("""
#                 # Section "Dependencies"

#                 %%capture

#                 import os
#                 import json
#                 import datetime
#                 import requests
#                 import getpass
#                 import pprint

#                 import numpy as np
#                 import pandas as pd

#                 !pip install zarr xarray
#                 import xarray as xr

#                 !pip install s3fs
#                 import s3fs

#                 !pip install "cdsapi>=0.7.4"
#                 import cdsapi
                
#                 !pip install cartopy
#                 import cartopy.crs as ccrs
#                 import cartopy.feature as cfeature
#             """),
#             nbf.v4.new_code_cell("""
#                 # Section "Define constant"

#                 # Forcast variables
#                 fc_variables = {variables}
                
#                 # Bouning box of interest in format [min_lon, min_lat, max_lon, max_lat]
#                 region = {area}

#                 # init forecast datetime
#                 init_time = datetime.datetime.strptime('{init_time}', "%Y-%m-%d").replace(day=1)

#                 # lead forecast datetime
#                 lead_time = datetime.datetime.strptime('{lead_time}', "%Y-%m-%d").replace(day=1)

#                 # ingested data ouput zarr file
#                 zarr_output = '{zarr_output}'
#             """),
#             nbf.v4.new_code_cell("""
#                 # Section "Call I-Cisk cds-ingestor-process API"

#                 # Prepare payload
#                 icisk_api_payload = {{
#                     "inputs": {{
#                         "dataset": "seasonal-original-single-levels",
#                         "file_out": f"/tmp/{{zarr_output.replace('.zarr', '')}}.nc",
#                         "query": {{
#                             "originating_centre": "ecmwf",
#                             "system": "51",
#                             "variable": fc_variables,
#                             "year": [f"{{init_time.year}}"],
#                             "month": [f"{{init_time.month:02d}}"],
#                             "day": ["01"],
#                             "leadtime_hour": [str(h) for h in range(24, int((lead_time - init_time).total_seconds() // 3600), 24)],
#                             "area": [
#                                 region[3],
#                                 region[0],
#                                 region[1],
#                                 region[2]
#                             ],
#                             "data_format": "netcdf",
#                         }},
#                         "token": "YOUR-ICISK-API-TOKEN",
#                         "zarr_out": f"s3://saferplaces.co/test/icisk/ai-agent/{{zarr_output}}",
#                     }}
#                 }}

#                 print(); print('-------------------------------------------------------------------'); print();

#                 pprint.pprint(icisk_api_payload)

#                 print(); print('-------------------------------------------------------------------'); print();

#                 icisk_api_token = 'token' # getpass.getpass("YOUR ICISK-API-TOKEN: ")

#                 icisk_api_payload['inputs']['token'] = icisk_api_token

#                 # Call API
#                 root_url = 'NGROK-URL' # 'https://i-cisk.dev.52north.org/ingest'
#                 icisk_api_response = requests.post(
#                     url = f'{{root_url}}/processes/ingestor-cds-process/execution',
#                     json = icisk_api_payload
#                 )

#                 # Display response
#                 pprint.pprint({{
#                     'response': icisk_api_response.json(),
#                     'status_code': icisk_api_response.status_code,
#                 }})
#             """),
#             nbf.v4.new_code_cell("""
#                 # Section "Get data from I-Cisk collection"

#                 living_lab = None
#                 collection_name = f"seasonal-original-single-levels_{{init_time.strftime('%Y%m')}}_{{living_lab}}_{icisk_varname}_0"

#                 # Query collection
#                 collection_response = requests.get(
#                     f'{{root_url}}/collections/{{collection_name}}/cube',
#                     params = {{
#                         'bbox': ','.join(map(str, region)),
#                         'f': 'json'
#                     }}
#                 )

#                 # Get response
#                 if collection_response.status_code == 200:
#                     collection_data = collection_response.json()
#                 else:
#                     print(f'Error {{collection_response.status_code}}: {{collection_response.json()}}')
#             """),
#             nbf.v4.new_code_cell("""
#                 # Section "Build dataset"

#                 # Parse collection output data
#                 axes = collection_data['domain']['axes']
#                 dims = {{
#                     'model': list(map(int, [p.split('_')[1] for p in params])),
#                     'time': pd.date_range(axes['time']['start'], axes['time']['stop'], axes['time']['num']),
#                     'lon': np.linspace(axes['x']['start'], axes['x']['stop'], axes['x']['num'], endpoint=True),
#                     'lat': np.linspace(axes['y']['start'], axes['y']['stop'], axes['y']['num'], endpoint=True)
#                 }}

#                 params = collection_data['parameters']
#                 ranges = collection_data['ranges']
#                 vars = {{
#                     '{icisk_varname}': (tuple(dims.keys()), np.stack([ np.array(ranges[name]['values']).reshape((len(dims['time']), len(dims['lon']), len(dims['lat']))) for name in params ]) )
#                 }}

#                 # Build xarray dataset
#                 dataset = xr.Dataset(
#                     data_vars = vars,
#                     coords = dims
#                 )
#             """),
#             nbf.v4.new_code_cell("""
#                 # Section "Describe dataset"

#                 \"\"\"
#                 Object "dataset" is a xarray.Dataset
#                 It has  three dimensions named:
#                 - 'model': list of model ids 
#                 - 'lat': list of latitudes, 
#                 - 'lon': list of longitudes,
#                 - 'time': forecast timesteps
#                 It has 1 variables named {icisk_varname} representing the {cds_varname} forecast data. It has a shape of [model, time, lat, lon].
#                 \"\"\"

#                 # Use this dataset variable to do next analysis or plots

#                 display(dataset)
#             """)
#         ]
        

#     def _run(
#         self, 
#         variables: None | list[CDSForecastVariable],
#         area: None | str | list[float],
#         init_time: None | str,
#         lead_time: None | str,
#         zarr_output: None | str,
#         run_manager: None | Optional[CallbackManagerForToolRun] = None
#     ) -> dict:
        
#         def controls_before_execution():
#             tool_args = {
#                 "variables": variables,
#                 "area": area,
#                 "init_time": init_time,
#                 "lead_time": lead_time,
#                 "zarr_output": zarr_output
#             }
#             self.check_required_args(tool_args)     # 1. Required arguments
#             self.check_invalid_args(tool_args)      # 2. Invalid arguments
#             self.infer_and_confirm_args(tool_args)  # 3. Infer and confirm arguments
            
#         controls_before_execution()
        
#         self.create_notebook()
        
#         nb_values = {
#             'variables': [self.CDSForecastVariable(var).as_cds for var in variables],
#             'area': area,
#             'init_time': init_time,
#             'lead_time': lead_time,
#             'zarr_output': zarr_output,
            
#             'cds_varname': self.CDSForecastVariable(variables[0]).as_cds,
#             'icisk_varname': self.CDSForecastVariable(variables[0]).as_icisk,
#         }

#         for cell in self.notebook.cells:
#             if cell.cell_type in ("markdown", "code"):
#                 code = cell.source.format(**nb_values)
#                 lines = code.split('\n')
#                 if len(lines) > 0:
#                     while lines[0] == '':
#                         lines = lines[1:]
#                     while lines[-1] == '':
#                         lines = lines[:-1]
#                     spaces = re.match(r'^\s*', lines[0])
#                     spaces = len(spaces.group()) if spaces else 0
#                     lines = [line[spaces:] for line in lines]
#                     lines = [f'{line}\n' if idx!=len(lines)-1 else f'{line}' for idx,line in enumerate(lines)]
#                 code = ''.join(lines)
#                 cell.source = code
        
#         notebook_path = os.path.join(utils._temp_dir, f'{utils.juststem(zarr_output)}.ipynb')
#         nbf.write(self.notebook, notebook_path)   
        
#         return {
#             "data_source": zarr_output,
#             "notebook": notebook_path,
#         }
        
        
# class CDSForecastIngestorCodeEditorTool(BaseTool):
    
#     class InputSchema(BaseModel):  # TODO: Better description
        
#         source: None | str = Field(
#             title = "Source",
#             description = "The code to be edited. It could be a python notebbok, a script.py. If not specified use None as default.",
#             examples = [
#                 None,
#                 'C:/path/to/python_script.py',
#                 'C:/path/to/python_notebook.ipynb'
#             ]
#         )
#         code_request: None | str | list[str] = Field(
#             title="Request",
#             description="""Meaning and usefulness of the requested code""",
#             examples=[
#                 None,
#                 "Please add a function to plot the data.",
#                 "Please add a function to save the data in a different format.",
#                 [ "Please add a function to filter the data.", "Plot data by category" ]
#             ]
#         )
    
    
#     name: str = CDS_INGESTOR_FORECAST_CODE_EDITOR_TOOL
#     description: str = """Useful when user want to edit the code of a notebook regarding CDS forecast data ingestor tool."""
#     args_schema: Optional[ArgsSchema] = InputSchema
#     return_direct: bool = True
    
#     extra_args: dict = dict()
    
#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)
#         self.extra_args = {
#             'execution_confirmed': False,
#             'output_confirmed': False,
#             'output': None,
#         }
        
        
#     def check_required_args(self, tool_args):
#         missing_args = [arg for arg in list(self.args_schema.model_fields.keys()) if tool_args[arg] is None]
        
#         if len(missing_args) > 0:
#             self.extra_args['execution_confirmed'] = False
#             raise ToolInterrupt(
#                 interrupt_tool = self.name,
#                 interrupt_type = ToolInterrupt.ToolInterruptType.PROVIDE_ARGS,
#                 interrupt_reason = f"Missing required arguments: {missing_args}.",
#                 interrupt_data = {
#                     "missing_args": missing_args,
#                     "args_schema": self.args_schema.model_fields
#                 }
#             )
            
        
#     def check_invalid_args(self, tool_args):
#         invalid_args = dict()
        
#         source = tool_args.get('source', None)
#         code_request = tool_args.get('code_request', None)
        
#         if source is not None:
#             if not os.path.exists(source) or \
#             not(source.endswith('.py') or source.endswith('.ipynb')):
#                 invalid_args['source'] = f"Invalid source: {source}. It should be a valid path to a python script or jupyter notebook."
            
#         if len(invalid_args) > 0:
#             self.extra_args['execution_confirmed'] = False
#             raise ToolInterrupt(
#                 interrupt_tool = self.name,
#                 interrupt_type = ToolInterrupt.ToolInterruptType.INVALID_ARGS,
#                 interrupt_reason = f"Invalid arguments: {list(invalid_args.keys())}.",
#                 interrupt_data = {
#                     "invalid_args": invalid_args,
#                     "args_schema": self.args_schema.model_fields
#                 }
#             )
        
    
#     def infer_and_confirm_args(self, tool_args):
#         source = tool_args.get('source', None)
#         code_request = tool_args.get('code_request', None)
        
#         # INFO: No args to infer .. cormi later with 'confirm output'
#         self.extra_args['execution_confirmed'] = True
            
    
#     def output_confirm(self, tool_args, tool_output):
#         return None # TODO: this for preview the code before execution (writing)
    
    
#     def _run(
#         self, 
#         source: None | str,
#         code_request: None | str | list[str],
#         run_manager: None | Optional[CallbackManagerForToolRun] = None
#     ) -> dict:
        
#         def controls_before_execution():
#             tool_args = {
#                 "source": source,
#                 "code_request": code_request
#             }
#             self.check_required_args(tool_args)     # 1. Required arguments
#             self.check_invalid_args(tool_args)      # 2. Invalid arguments
#             self.infer_and_confirm_args(tool_args)  # 3. Infer and confirm arguments
            
#         controls_before_execution()
        
#         def get_source_code():
#             if source.endswith('.ipynb'):
#                 nb = nbf.read(source, as_version=4)
#                 source_code = [cell.source for cell in nb.cells if cell.cell_type == 'code' and cell.source != '']
#                 source_code = '\n'.join(source_code)
#             elif source.endswith('.py'):
#                 with open(source, 'r') as f:
#                     source_code = f.read().split('\n')
#             return source_code
        
#         def add_source_code(source_code):
#             if source.endswith('.ipynb'):
#                 nb = nbf.read(source, as_version=4)
#                 new_cell = new_code_cell(source = source_code)
#                 nb.cells.append(new_cell)
#                 nbf.write(nb, source)
#             elif source.endswith('.py'):
#                 with open(source, 'a') as f:
#                     f.write('\n')
#                     f.write('# Code from ICisk AI Agent ----------------------------------------------------\n')
#                     f.write(source_code)
#                     f.write('\n')
#                     f.write('-------------------------------------------------------------------------------\n')
        
#         if not self.extra_args['output_confirmed']:
            
#             generated_code = utils.ask_llm(
#                 role = 'system',
#                 message = f"""
#                     You are a programming assistant who helps users write python code.
#                     Remember that the code is related to an analysis of geospatial data. If map visualizations are requested, use the cartopy library, adding borders, coastlines, lakes and rivers.

#                     You have been asked to write python code that satisfies the following request:

#                     {code_request}

#                     The code produced must be added to this existing code:

#                     {get_source_code()}

#                     ------------------------------------------

#                     Respond only with python code that can be integrated with the existing code. It must use the appropriate variables already defined in the code.
#                     Do not attach any other text.
#                     Do not produce additional code other than that necessary to satisfy the requests declared in the parameter.
#                 """,
#                 eval_output = False
#             )
#             self.extra_args['output'] = generated_code
            
#             raise ToolInterrupt(
#                 interrupt_tool = self.name,
#                 interrupt_type = ToolInterrupt.ToolInterruptType.CONFIRM_OUTPUT,
#                 interrupt_reason = "A user confirmation of the generated code is required.",
#                 interrupt_data = {
#                     "output": {
#                         'generated_code': generated_code
#                     }
#                 }
#             )
        
#         else:
#             generated_code = self.extra_args['output']['generated_code']
#             add_source_code(generated_code)
                        
#         return {
#             "generated_code" : generated_code
#         }

