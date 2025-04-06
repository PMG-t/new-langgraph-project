# DOC: Tool for creating a new notebook in for SPI calculation

import os
import re
import json

from langchain_core.tools import tool
from agent import utils


@tool()
def spi_notebook_creation(
    region: str | list = None,
    reference_period: tuple = None,
    period_of_interest: tuple = None,
):
    """
    Build a new Jupyter notebook for calculating the Standardized Precipitation Index (SPI) for a given region and return the path where the notebook is saved.
    The tool uses the Climate Data Store (CDS) API to retrieve the necessary data from "ERA5-Land monthly averaged data from 1950 to present" dataset
    Use this tool when user asks for an help in SPI calculation even if user does not provide region.

    Args:
        location: list of four elements representing a bounding box (min_lon, min_lat, max_lon, max_lat) or name of a region (could be also geographic part of a whole nation or region).
        reference_period: tuple of two elements representing the start and end year of the reference period. Default is (1981, 2010)
        period_of_interest: tuple of two elements representing the start and end month of the period of interest for which SPI has to be calculated. Their value is in a string format "YYYY-MM". Default is the previous month from the current date.
    """
    
    notebook_sections = [
        {
            "title": "install dependencies and import libs",
            "code": """
                import os
                import math
                import datetime
                from dateutil.relativedelta import relativedelta
                import getpass

                import numpy as np
                import pandas as pd
                import xarray as xr

                import scipy.stats as stats
                from scipy.special import gammainc, gamma
                
                import matplotlib.pyplot as plt

                !pip install "cdsapi>=0.7.4"
                import cdsapi
                
                !pip install cartopy
                import cartopy.crs as ccrs
                import cartopy.feature as cfeature
            """
        }, 
        {
            "title": "define costants",
            "code": f"""
                spi_ts = 1

                region = {region} # min_lon, min_lat, max_lon, max_lat

                reference_period = {reference_period} # start_year, end_year

                period_of_interest = {period_of_interest} # start_month, end_month

                cds_client = cdsapi.Client(url='https://cds.climate.copernicus.eu/api', key=getpass.getpass("YOUR CDS-API-KEY")) # CDS client
            """
        },
        {
            "title": "define functions",
            "code": """
                filename = f'era5_land__total_precipitation__{"_".join([str(c) for c in region])}__monthly__{reference_period[0]}_{reference_period[1]:02d}.nc'

                out_dir = 'tmpdir'
                os.makedirs(out_dir, exist_ok=True)

                cds_out_filename = os.path.join(out_dir, filename)

                if not os.path.exists(cds_out_filename):
                    cds_dataset = 'reanalysis-era5-land-monthly-means'
                    cds_query =  {
                        'product_type': 'monthly_averaged_reanalysis',
                        'variable': 'total_precipitation',
                        'year': [str(year) for year in range(*reference_period)],
                        'month': [f'{month:02d}' for month in range(1, 13)],
                        'time': '00:00',
                        'area': [
                            region[3],  # N
                            region[0],  # W
                            region[1],  # S
                            region[2]   # E
                        ],
                        "data_format": "netcdf",
                        "download_format": "unarchived"
                    }

                    cds_client.retrieve(cds_dataset, cds_query, cds_out_filename)

                cds_ref_data = xr.open_dataset(cds_out_filename)
            """
        },
        {
            "title": "Retrieve period of interest data from CDS",
            "code": """
                # Get (Years, Years-Months) couple for the CDS api query. (We can query just one month at time)
                period_of_interest = (datetime.datetime.strptime(period_of_interest[0], "%Y-%m"), datetime.datetime.strptime(period_of_interest[1], "%Y-%m"))
                spi_start_date = period_of_interest[0] - relativedelta(months=spi_ts-1)
                spi_years_range = list(range(spi_start_date.year, period_of_interest[1].year+1))
                spi_month_range = []
                for iy,year in enumerate(range(spi_years_range[0], spi_years_range[-1]+1)):
                    if iy==0 and len(spi_years_range)==1:
                        spi_month_range.append([month for month in range(spi_start_date.month, period_of_interest[1].month+1)])
                    elif iy==0 and len(spi_years_range)>1:
                        spi_month_range.append([month for month in range(spi_start_date.month, 13)])
                    elif iy>0 and iy==len(spi_years_range)-1:
                        spi_month_range.append([month for month in range(1, period_of_interest[1].month+1)])
                    else:
                        spi_month_range.append([month for month in range(1, 13)])

                def build_cds_hourly_data_filepath(year, month):
                    dataset_part = 'reanalysis_era5_land__total_precipitation__hourly'
                    time_part = f'{year}-{month[0]:02d}_{year}-{month[-1]:02d}'
                    filename = f'{dataset_part}__{"_".join([str(c) for c in region])}__{time_part}.nc'
                    filedir = os.path.join(out_dir, dataset_part)
                    if not os.path.exists(filedir):
                        os.makedirs(filedir, exist_ok=True)
                    filepath = os.path.join(filedir, filename)
                    return filepath

                def floor_decimals(number, decimals=0):
                    factor = 10 ** decimals
                    return math.floor(number * factor) / factor

                def ceil_decimals(number, decimals=0):
                    factor = 10 ** decimals
                    return math.ceil(number * factor) / factor

                # CDS API query
                cds_poi_data_filepaths = []
                for q_idx, (year,year_months) in enumerate(zip(spi_years_range, spi_month_range)):
                    for ym in year_months:
                        cds_poi_data_filepath = build_cds_hourly_data_filepath(year, [ym])
                        if not os.path.exists(cds_poi_data_filepath):
                            cds_dataset = 'reanalysis-era5-land'
                            cds_query =  {
                                'variable': 'total_precipitation',
                                'year': [str(year)],
                                'month': [f'{month:02d}' for month in year_months],
                                'day': [f'{day:02d}' for day in range(1, 32)],
                                'time': [f'{hour:02d}:00' for hour in range(0, 24)],
                                'area': [
                                    ceil_decimals(region[3], 1),    # N
                                    floor_decimals(region[0], 1),   # W
                                    floor_decimals(region[1], 1),   # S
                                    ceil_decimals(region[2], 1),    # E
                                ],
                                "data_format": "netcdf",
                                "download_format": "unarchived"
                            }
                            cds_client.retrieve(cds_dataset, cds_query, cds_poi_data_filepath)

                    print(f'{q_idx+1}/{len(year_months)}/{len(spi_years_range)} - CDS API query completed')
                    cds_poi_data_filepaths.append(cds_poi_data_filepath)

                cds_poi_data = [xr.open_dataset(fp) for fp in cds_poi_data_filepaths]
                cds_poi_data = xr.concat(cds_poi_data, dim='valid_time')
                cds_poi_data = cds_poi_data.sel(valid_time=(cds_poi_data.valid_time.dt.date>=period_of_interest[0].date()) & (cds_poi_data.valid_time.dt.date<=period_of_interest[1].date()))
            """
        },
        {
            "title": "Preprocess datasets",
            "code": """
                # Preprocess reference dataset
                cds_ref_data = cds_ref_data.drop_vars(['number', 'expver'])
                cds_ref_data = cds_ref_data.rename({'valid_time': 'time', 'latitude': 'lat', 'longitude': 'lon'})
                cds_ref_data = cds_ref_data * cds_ref_data['time'].dt.days_in_month
                cds_ref_data = cds_ref_data.assign_coords(
                    lat=np.round(cds_ref_data.lat.values, 6),
                    lon=np.round(cds_ref_data.lon.values, 6),
                )
                cds_ref_data = cds_ref_data.sortby(['time', 'lat', 'lon'])

                # Preprocess period-of-interest dataset
                cds_poi_data = cds_poi_data.drop_vars(['number', 'expver'])
                cds_poi_data = cds_poi_data.rename({'valid_time': 'time', 'latitude': 'lat', 'longitude': 'lon'})
                cds_poi_data = cds_poi_data.resample(time='1ME').sum()                                   # Resample to monthly total data
                cds_poi_data = cds_poi_data.assign_coords(time=cds_poi_data.time.dt.strftime('%Y-%m-01'))  # Set month day to 01
                cds_poi_data = cds_poi_data.assign_coords(time=pd.to_datetime(cds_poi_data.time))
                cds_poi_data['tp'] = cds_poi_data['tp'] / 12                                              # Convert total precipitation to monthly average precipitation
                cds_poi_data = cds_poi_data.assign_coords(
                    lat=np.round(cds_poi_data.lat.values, 6),
                    lon=np.round(cds_poi_data.lon.values, 6),
                )
                cds_poi_data = cds_poi_data.sortby(['time', 'lat', 'lon'])

                # Get whole dataset
                ts_dataset = xr.concat([cds_ref_data, cds_poi_data], dim='time')
                ts_dataset = ts_dataset.drop_duplicates(dim='time').sortby(['time', 'lat', 'lon'])
            """
        },
        {
            "title": "SPI calculation",
            "code": """
                # Compute SPI function
                def compute_timeseries_spi(monthly_data, spi_ts, nt_return=1):
                    # Compute SPI index for a time series of monthly data
                    # REF: https://drought.emergency.copernicus.eu/data/factsheets/factsheet_spi.pdf
                    # REF: https://mountainscholar.org/items/842b69e8-a465-4aeb-b7ec-021703baa6af [ page 18 to 24 ]
                    
                    # SPI calculation needs finite-values and non-zero values
                    if all([md<=0 for md in monthly_data]):
                        return 0
                    if all([np.isnan(md) or md==0 for md in monthly_data]):
                        return np.nan
                    
                    df = pd.DataFrame({'monthly_data': monthly_data})

                    # Totalled data over t_scale rolling windows
                    if spi_ts > 1:
                        t_scaled_monthly_data = df.rolling(spi_ts).sum().monthly_data.iloc[spi_ts:]
                    else:
                        t_scaled_monthly_data = df.monthly_data

                    # Gamma fitted params
                    a, _, b = stats.gamma.fit(t_scaled_monthly_data, floc=0)

                    # Cumulative probability distribution
                    G = lambda x: stats.gamma.cdf(x, a=a, loc=0, scale=b)

                    m = (t_scaled_monthly_data==0).sum()
                    n = len(t_scaled_monthly_data)
                    q = m / n # zero prob

                    H = lambda x: q + (1-q) * G(x) # zero correction

                    t = lambda Hx: math.sqrt(
                        math.log(1 /
                        (math.pow(Hx, 2) if 0<Hx<=0.5 else math.pow(1-Hx, 2))
                    ))

                    c0, c1, c2 = 2.515517, 0.802853, 0.010328
                    d1, d2, d3 = 1.432788, 0.189269, 0.001308

                    Hxs = t_scaled_monthly_data[-spi_ts:].apply(H)
                    txs = Hxs.apply(t)

                    Z = lambda Hx, tx: ( tx - ((c0 + c1*tx + c2*math.pow(tx,2)) / (1 + d1*tx + d2*math.pow(tx,2) + d3*math.pow(tx,3) )) ) * (-1 if 0<Hx<=0.5 else 1)

                    spi_t_indexes = pd.DataFrame(zip(Hxs, txs), columns=['H','t']).apply(lambda x: Z(x.H, x.t), axis=1).to_list()

                    return np.array(spi_t_indexes[-nt_return]) if nt_return==1 else np.array(spi_t_indexes[-nt_return:])

                # Compute SPI over each cell
                month_spi_coverages = []
                for month in cds_poi_data.time:
                    month_spi_coverage = xr.apply_ufunc(
                        lambda tile_timeseries: compute_timeseries_spi(tile_timeseries, spi_ts=spi_ts, nt_return=1),
                        ts_dataset.sel(time=ts_dataset.time<=month).tp.sortby('time'),
                        input_core_dims = [['time']],
                        vectorize = True
                    )
                    month_spi_coverages.append((
                        month.dt.date.item(),
                        month_spi_coverage
                    ))

                # Create SPI dataset
                spi_times = [msc[0] for msc in month_spi_coverages]
                spi_grids = [msc[1] for msc in month_spi_coverages]

                spi_dataset = xr.concat(spi_grids, dim='time').to_dataset()
                spi_dataset = spi_dataset.assign_coords({'time': spi_times})
                spi_dataset = spi_dataset.rename_vars({'tp': 'spi'})

                spi_values = spi_dataset.spi.values
            """
        },
        {
            "title": "Extract SPI values for next elaborations",
            "code": """
                # variable "spi_dataset" is a xarray.Dataset with three dimensions ('time', 'lat', 'lon') and a 'spi' var related to those dimensions
                display(spi_dataset)

                # variable "spi_values" is a numpy.array with shape (time, lat, lon) and it is representig numerical values of spi index over each time for each lat-lon cell
                display(spi_values) 
            """
        }
    ]
    
    ipynb_filename = os.path.join(utils._temp_dir, f'spi_{region}_notebook.ipynb')
    
    def safe_code(code):
        lines = [line for line in code.split('\n')]
        while lines[0] == '':
            lines = lines[1:]
        while lines[-1] == '':
            lines = lines[:-1]
        spaces = re.match(r'^\s*', lines[0])
        spaces = len(spaces.group()) if spaces else 0
        lines = [line[spaces:] for line in lines]
        lines = [f'{line}\n' if idx!=len(lines)-1 else f'{line}' for idx,line in enumerate(lines)]
        return lines   
        
    ipynb_cells = [
        {
            "cell_type": "code",
            "execution_count": 1,
            "metadata": dict(),
            "outputs": [
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "... Run to see results ..."
                    ]
                }
            ],
            "source": safe_code(section['code'])
        }
        for section in notebook_sections
    ]
    ipynb_json = {
        "cells": ipynb_cells,
        "metadata": dict(),
        "nbformat": 4,
        "nbformat_minor": 2
    }
    
    with open(ipynb_filename, 'w') as f:
        json.dump(ipynb_json, f)
    
    return ipynb_filename



@tool()
def spi_notebook_editor(notebook_path: str = None, code_request: str = None):
    """
    Edit an existing Jupyter notebook related to Standardized Precipitation Index (SPI) by adding new code lines. It must be provided as an absolute path in local filesystem.
    Use this tool when user asks for an help in SPI calculation and wants to edit the notebook by adding something new.

    Args:
        notebook_path: path of the Jupyter notebook to edit
        code_request: meaning and usefulness of the requested code
    """
    
    def clean_code_block(text):
        """Rimuove eventuali delimitatori di codice markdown (``` e ```python) da un blocco di codice."""
        return re.sub(r"^```(?:python)?\n|\n```$", "", text, flags=re.MULTILINE)

    
    with open(notebook_path, 'r', encoding='utf-8') as f:
        ipynb_json = json.loads(f.read())
        cells = ipynb_json.get('cells', [])
        notebook_source_code = '\n'.join(['\n'.join(cell['source']) for cell in cells])
        
        prompt = f"""
            You are a programming assistant who helps users write python code.
            Remember that the code is related to an analysis of geospatial data. If map visualizations are requested, use the cartopy library, adding borders, coastlines, lakes and rivers.

            You have been asked to write python code that satisfies the following request:

            {code_request}

            The code produced must be added to this existing code:

            {notebook_source_code}

            ------------------------------------------

            Respond only with python code that can be integrated with the existing code. It must use the appropriate variables already defined in the code.
            Do not attach any other text.
            Do not produce additional code other than that necessary to satisfy the requests declared in the parameter.
        """
        
        prompt_out = utils._base_llm.invoke([{"type": "system", "content": prompt}])
        code_lines = clean_code_block(prompt_out.content).split('\n')
            
            
    def safe_code(lines):
        spaces = re.match(r'^\s*', lines[0])
        spaces = len(spaces.group()) if spaces else 0
        lines = [line[spaces:] for line in lines]
        lines = [f'{line}\n' for line in lines]
        return lines  
    
    try:
        ipynb_json = None
        with open(notebook_path, 'r', encoding='utf-8') as f:
            ipynb_json = json.load(f)

        cells = ipynb_json.get('cells', [])
        if code_lines:
            new_cell = {
                "cell_type": "code",
                "execution_count": None,
                "metadata": dict(),
                "outputs": [],
                "source": safe_code(code_lines)
            }
            cells.append(new_cell)  
        ipynb_json['cells'] = cells
        
        with open(notebook_path, 'w') as f:
            json.dump(ipynb_json, f)
    
        return notebook_path
    except Exception as e:
        print('\n\n\n\n\n')
        print(e)
        print('\n\n\n\n\n')
        return "File not found or not a valid Jupyter notebook"
        
    