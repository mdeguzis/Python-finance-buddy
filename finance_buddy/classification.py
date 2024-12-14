import logging
from enum import Enum

# Initialize logging
logger = logging.getLogger(__name__)


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
