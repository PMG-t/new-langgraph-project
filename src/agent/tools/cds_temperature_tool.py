import datetime

from langchain_core.tools import tool

cds_temperature_descriptors = {
    "tool": """Build a new Jupyter notebook for gathering temperature forecast data.
    Return the path name of the notebook created.
    Use this tool when user asks for an help with temperature data retrieving even if user does not provide the input arguments.""",
    
    "args": {
        "location": """list of four elements representing a bounding box (min_lon, min_lat, max_lon, max_lat) in EPSG:4326 as Coordinate-Reference-System (CRS).""",
        "init_time": """time representing the forecast init month. It should be in the format 'YYYY-MM'. Default is the current month.""",
        "lead_time": """time representing the forecast lead month. It should be in the format 'YYYY-MM'. Default is six months ahead from the init_time.""",
        "zarr_output_file": """the name of the zarr file to save the data."""
    }
}

@tool()
def cds_temperature(
    location: list = None,
    init_time: str = None,
    lead_time: str = None,
    zarr_output_file: str = None
):
    """
    Build a new Jupyter notebook for gathering temperature forecast data.
    Return the path name of the notebook created.
    Use this tool when user asks for an help with temperature data retrieving even if user does not provide the input arguments.
    
    Args:
        location: list of four elements representing a bounding box (min_lon, min_lat, max_lon, max_lat) in EPSG:4326 as Coordinate-Reference-System (CRS).
        init_time: time representing the forecast init month. It should be in the format 'YYYY-MM'. Default is the current month.
        lead_time: time representing the forecast lead month. It should be in the format 'YYYY-MM'. Default is six months ahead from the init_time.
        zarr_output_file: the name of the zarr file to save the data.
    """
    return 'fake-temperature-notebook.ipynb'