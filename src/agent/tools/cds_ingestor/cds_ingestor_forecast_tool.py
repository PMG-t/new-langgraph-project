import os
import datetime
from enum import Enum

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


# DOC: This is a tool that exploits I-Cisk API to ingests forecast data from the Climate Data Store (CDS) API and saves it in a zarr format. It build a jupyter notebook to do that.
class CDSIngestorForecastTool(BaseAgentTool):
    
    
    # DOC: CDS Variable names
    class InputForecastVariable(str, Enum):
    
        precipitation = "total-precipitation"
        temperature = "temperature"
        min_temperature = "minimum-temperature"
        max_temperature = "maximum-temperature"
        glofas = "glofas" # TODO: give a better name(s)
        
        @property
        def as_cds(self) -> str:
            return {
                'total-precipitation': 'total_precipitation',
                'temperature': '2m_temperature',
            }.get(self.value)
            
        @property
        def as_icisk(self) -> str:
            return {
                'total-precipitation': 'tp',
                'temperature': 't2m',
            }.get(self.value)
        
    
    # DOC: Tool input schema
    class InputSchema(BaseModel):
        
        forecast_variables: None | list[str] = Field(
            title = "Forecast-Variables",
            description = "List of forecast variables to be retrieved from the CDS API. If not specified use None as default.",
            examples   = [
                None,
                ['total-precipitation'],
                ['minimum-temperature', 'maximum-temperature'],
                ['total-precipitation', 'glofas'],
            ]
        )
        area: None | str | list[float] = Field(
            title = "Area",
            description = """The area of interest for the forecast data. If not specified use None as default.
            It   could be a bouning-box defined by [min_x, min_y, max_x, max_y] coordinates provided in EPSG:4326 Coordinate Reference System.
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
            title = "Initialization Time",
            description = f"The date of the forecast initialization provided in UTC-0 YYYY-MM-DD. If not specified use {datetime.datetime.now().strftime('%Y-%m-01')} as default.",
            examples = [
                None,
                "2025-01-01",
                "2025-02-01",
                "2025-03-10",
            ]
        )
        lead_time: None | str = Field(
            title = "Lead Time",
            description = f"The end date of the forecast lead time provided in UTC-0 YYYY-MM-DD. If not specified use: {(datetime.datetime.now().date().replace(day=1) + datetime.timedelta(days=31)).strftime('%Y-%m-01')} as default.",
            examples = [
                None,
                "2023-02-01",
                "2023-03-01",
                "2023-04-10",
            ]
        )
        zarr_output: None | str = Field(
            title = "Output Zarr File",
            description = f"The path to the output zarr file with the forecast data. In could be a local path or a remote path. If not specified is None", #'icisk-ai_cds-ingestor-output.zarr' as default.",
            examples = [
                None,
                "C:/Users/username/appdata/local/temp/output-<variable>.zarr",
                "/path/to/output-<variable>-<date>.zarr",
                "S3://bucket-name/path/to/<location>-<varibale>-data.zarr",
            ],
            default = None
        )
        
    # DOC: Additional tool args
    notebook: nbf.NotebookNode = nbf.v4.new_notebook()

    
    # DOC: Initialize the tool with a name, description and args_schema
    def __init__(self, **kwargs):
        super().__init__(
            name = CDS_INGESTOR_FORECAST_TOOL,
            description = """Useful when user want to forecast data from the Climate Data Store (CDS) API.
            This tool builds a jupityer notebook to ingests forecast data for a specific region and time period, and saves it in a zarr format.
            It exploits I-CISK APIs to build data retrieval and storage by leveraging these CDS dataset:
            - "Seasonal-Original-Single-Levels" for the seasonal forecast of temperature and precipitation data.
            - "CEMS Early Warning Data Store" for the river discharge forecasting (GloFAS) data.
            This tool returns the path to the output zarr file with the retireved forecast data and an editable jupyter notebook that was used to build the data ingest procedure.
            If not provided by the user, assign the specified default values to the arguments.
            """,
            args_schema = CDSIngestorForecastTool.InputSchema,
            **kwargs
        )
        self.output_confirmed = True    # INFO: There is already the execution_confirmed:True
        
    
    # DOC: Validation rules ( i.e.: valid init and lead time ... ) 
    def _set_args_validation_rules(self) -> dict:
        
        return {
            'forecast_variables' : [
                lambda **ka: f"Invalid forecast variables: {ka['forecast_variables']}. By now only one variable is supported." 
                    if len(ka['forecast_variables']) > 1 else None,
                lambda **ka: f"Invalid forecast variables: {[v for v in ka['forecast_variables'] if v not in self.InputForecastVariable._member_names_]}. It should be a list of valid CDS forecast variables: {[self.InputForecastVariable._member_names_]}."
                    if len([v for v in ka['forecast_variables'] if v not in self.InputForecastVariable._member_names_]) > 0 else None 
            ],
            'area': [
                lambda **ka: f"Invalid area coordinates: {ka['area']}. It should be a list of 4 float values representing the bounding box [min_x, min_y, max_x, max_y]." 
                    if isinstance(ka['area'], list) and len(ka['area']) != 4 else None  
            ],
            'init_time': [
                lambda **ka: f"Invalid initialization time: {ka['init_time']}. It should be in the format YYYY-MM-DD."
                    if utils.try_default(lambda: datetime.datetime.strptime(ka['init_time'], "%Y-%m-%d"), None) is None else None,
                lambda **ka: f"Invalid initialization time: {ka['init_time']}. It should be in the past, at least in the previous month."
                    if datetime.datetime.strptime(ka['init_time'], '%Y-%m-%d') > datetime.datetime.now() else None
            ],
            'lead_time': [
                lambda **ka: f"Invalid lead time: {ka['lead_time']}. It should be in the format YYYY-MM-DD."
                    if utils.try_default(lambda: datetime.datetime.strptime(ka['lead_time'], "%Y-%m-%d"), None) is None else None,
                lambda **ka: f"Invalid lead time: {ka['lead_time']}. It should be in the after the init time."
                    if utils.try_default(lambda: datetime.datetime.strptime(ka['lead_time'], '%Y-%m-%d') < datetime.datetime.strptime(ka['init_time'], '%Y-%m-%d'), False) else None,
            ],
            'zarr_output': [
                lambda **ka: f"Invalid output path: {ka['zarr_output']}. It should be a valid zarr file path."
                    if ka['zarr_output'] is not None and not ka['zarr_output'].lower().endswith('.zarr') else None
            ]
        }
        
    
    # DOC: Inference rules ( i.e.: from location name to bbox ... )
    def _set_args_inference_rules(self) -> dict:
        
        def infer_area(**ka):
            def bounding_box_from_location_name(area):
                if type(area) is str:
                    area = utils.ask_llm(
                        role = 'system',
                        message = f"""Please provide the bounding box coordinates for the area: {area} with format [min_x, min_y, max_x, max_y] in EPSG:4326 Coordinate Reference System. 
                        Provide only the coordinates list without any additional text or explanation.""",
                        eval_output = True
                    )
                return area
            return bounding_box_from_location_name(ka['area'])
        
        def infer_zarr_output(**ka):
            if ka['zarr_output'] is None:
                return f"icisk-ai_cds-ingestor-forecast_{ka['forecast_variables'][0]}_{datetime.datetime.now().isoformat(timespec='seconds').replace(':','-')}.zarr"
            return ka['zarr_output']
        
        return {
            'area': infer_area,
            'zarr_output': infer_zarr_output
        }
        
    
    # DOC: Preapre notebook cell code template
    def create_notebook(self):
        self.notebook.cells = [
            nbf.v4.new_code_cell("""
                # Section "Dependencies"

                %%capture

                import os
                import json
                import datetime
                import requests
                import getpass
                import pprint

                import numpy as np
                import pandas as pd

                !pip install zarr xarray
                import xarray as xr

                !pip install s3fs
                import s3fs

                !pip install "cdsapi>=0.7.4"
                import cdsapi
                
                !pip install cartopy
                import cartopy.crs as ccrs
                import cartopy.feature as cfeature
            """),
            nbf.v4.new_code_cell("""
                # Section "Define constant"

                # Forcast variables
                forecast_variables = {forecast_variables}
                
                # Bouning box of interest in format [min_lon, min_lat, max_lon, max_lat]
                region = {area}

                # init forecast datetime
                init_time = datetime.datetime.strptime('{init_time}', "%Y-%m-%d").replace(day=1)

                # lead forecast datetime
                lead_time = datetime.datetime.strptime('{lead_time}', "%Y-%m-%d").replace(day=1)

                # ingested data ouput zarr file
                zarr_output = '{zarr_output}'
            """),
            nbf.v4.new_code_cell("""
                # Section "Call I-Cisk cds-ingestor-process API"

                # Prepare payload
                icisk_api_payload = {{
                    "inputs": {{
                        "dataset": "seasonal-original-single-levels",
                        "file_out": f"/tmp/{{zarr_output.replace('.zarr', '')}}.nc",
                        "query": {{
                            "originating_centre": "ecmwf",
                            "system": "51",
                            "variable": forecast_variables,
                            "year": [f"{{init_time.year}}"],
                            "month": [f"{{init_time.month:02d}}"],
                            "day": ["01"],
                            "leadtime_hour": [str(h) for h in range(24, int((lead_time - init_time).total_seconds() // 3600), 24)],
                            "area": [
                                region[3],
                                region[0],
                                region[1],
                                region[2]
                            ],
                            "data_format": "netcdf",
                        }},
                        "token": "YOUR-ICISK-API-TOKEN",
                        "zarr_out": f"s3://saferplaces.co/test/icisk/ai-agent/{{zarr_output}}",
                    }}
                }}

                print(); print('-------------------------------------------------------------------'); print();

                pprint.pprint(icisk_api_payload)

                print(); print('-------------------------------------------------------------------'); print();

                icisk_api_token = 'token' # getpass.getpass("YOUR ICISK-API-TOKEN: ")

                icisk_api_payload['inputs']['token'] = icisk_api_token

                # Call API
                root_url = 'NGROK-URL' # 'https://i-cisk.dev.52north.org/ingest'
                icisk_api_response = requests.post(
                    url = f'{{root_url}}/processes/ingestor-cds-process/execution',
                    json = icisk_api_payload
                )

                # Display response
                pprint.pprint({{
                    'response': icisk_api_response.json(),
                    'status_code': icisk_api_response.status_code,
                }})
            """),
            nbf.v4.new_code_cell("""
                # Section "Get data from I-Cisk collection"

                living_lab = None
                collection_name = f"seasonal-original-single-levels_{{init_time.strftime('%Y%m')}}_{{living_lab}}_{icisk_varname}_0"

                # Query collection
                collection_response = requests.get(
                    f'{{root_url}}/collections/{{collection_name}}/cube',
                    params = {{
                        'bbox': ','.join(map(str, region)),
                        'f': 'json'
                    }}
                )

                # Get response
                if collection_response.status_code == 200:
                    collection_data = collection_response.json()
                else:
                    print(f'Error {{collection_response.status_code}}: {{collection_response.json()}}')
            """),
            nbf.v4.new_code_cell("""
                # Section "Build dataset"

                # Parse collection output data
                axes = collection_data['domain']['axes']
                dims = {{
                    'model': list(map(int, [p.split('_')[1] for p in params])),
                    'time': pd.date_range(axes['time']['start'], axes['time']['stop'], axes['time']['num']),
                    'lon': np.linspace(axes['x']['start'], axes['x']['stop'], axes['x']['num'], endpoint=True),
                    'lat': np.linspace(axes['y']['start'], axes['y']['stop'], axes['y']['num'], endpoint=True)
                }}

                params = collection_data['parameters']
                ranges = collection_data['ranges']
                vars = {{
                    '{icisk_varname}': (tuple(dims.keys()), np.stack([ np.array(ranges[name]['values']).reshape((len(dims['time']), len(dims['lon']), len(dims['lat']))) for name in params ]) )
                }}

                # Build xarray dataset
                dataset = xr.Dataset(
                    data_vars = vars,
                    coords = dims
                )
            """),
            nbf.v4.new_code_cell("""
                # Section "Describe dataset"

                \"\"\"
                Object "dataset" is a xarray.Dataset
                It has  three dimensions named:
                - 'model': list of model ids 
                - 'lat': list of latitudes, 
                - 'lon': list of longitudes,
                - 'time': forecast timesteps
                It has 1 variables named {icisk_varname} representing the {cds_varname} forecast data. It has a shape of [model, time, lat, lon].
                \"\"\"

                # Use this dataset variable to do next analysis or plots

                display(dataset)
            """)
        ]
    
    
    # DOC: Execute the tool → Build notebook, write it to a file and return the path to the notebook and the zarr output file
    def _execute(
        self,
        forecast_variables: list[InputForecastVariable],
        area: str | list[float],
        init_time: str,
        lead_time: str,
        zarr_output: str
    ): 
        self.create_notebook()    
        nb_values = {
            'forecast_variables': [self.InputForecastVariable(var).as_cds for var in forecast_variables],
            'area': area,
            'init_time': init_time,
            'lead_time': lead_time,
            'zarr_output': zarr_output,
            
            'cds_varname': self.InputForecastVariable(forecast_variables[0]).as_cds,
            'icisk_varname': self.InputForecastVariable(forecast_variables[0]).as_icisk,
        }
        for cell in self.notebook.cells:
            if cell.cell_type in ("markdown", "code"):
                cell.source = utils.safe_code_lines(cell.source, format_dict=nb_values)
        notebook_path = os.path.join(utils._temp_dir, f'{utils.juststem(zarr_output)}.ipynb')
        nbf.write(self.notebook, notebook_path) 
        
        return {
            "data_source": zarr_output,
            "notebook": notebook_path,
        }
        
    
    # DOC: Try running AgentTool → Will check required, validity and inference over arguments thatn call and return _execute()
    def _run(
        self, 
        forecast_variables: list[InputForecastVariable],
        area: str | list[float],
        init_time: str,
        lead_time: str,
        zarr_output: str = None,
        run_manager: None | Optional[CallbackManagerForToolRun] = None
    ) -> dict:
        
        return super()._run(
            tool_args = {
                "forecast_variables": forecast_variables,
                "area": area,
                "init_time": init_time,
                "lead_time": lead_time,
                "zarr_output": zarr_output
            },
            run_manager=run_manager
        )