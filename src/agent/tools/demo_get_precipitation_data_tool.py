# DOC: dummy total precipitation tool (returns the sum of the length of location and day)

import datetime
from langchain_core.tools import tool



@tool()
def demo_get_precipitation_data(location: str = None, date: str = None):
    """
    Get the precipitation intenisity measures in millimeters per hour for a given location in a specified date.
    Use this tool when user asks for precipitation data even if user does not provide location and date.

    Args:
        location: location name
        date: date in format YYYY-MM-DD
    """
    return len(location) + datetime.datetime.strptime(date, "%Y-%m-%d").date().day