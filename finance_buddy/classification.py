import logging
from enum import Enum

# Define an Enum for expense categories
class ExpenseCategory(Enum):
    RENT = "rent"
    UTILITIES = "utilities"
    GROCERIES = "groceries"
    TRANSPORTATION = "transportation"
    ENTERTAINMENT = "entertainment"
    HEALTHCARE = "healthcare"
    MISCELLANEOUS = "miscellaneous"
    UNKNOWN = "unknown"