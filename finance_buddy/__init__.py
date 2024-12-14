"""
Python Finance Buddy
---------------------
A multi-user focused budget analysis / planning tool.

GitHub: https://github.com/mdeguzis/Python-finance-buddy
"""

# Import specific functions or classes for convenience
# None

# Define the package version
__version__ = "1.0.0"

# Define what gets exposed when using `from finance_buddy import *`
# __all__ = [
#    "calculate_interest",
#    "loan_amortization",
#    "analyze_portfolio",
#    "calculate_risk",
#    "fetch_market_data",
# ]

# Stick to a simple import for now
from .capital_one import *
from .classification import *
from .utils import *
