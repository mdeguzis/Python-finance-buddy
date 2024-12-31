from decimal import Decimal
import logging
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import json
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
import json


logger = logging.getLogger(__name__)


def initialize_logger(
    log_level=logging.INFO,
    log_filename=None,
    propagate=False,
    scope=None,
    formatter="%(asctime)s - %(levelname)s - %(message)s",
):
    """
    Initializes a logger for both stdout and to-file
    Returns the logger in-case a scope of non root is used

    Parameters
    ----------
    log_level:      Allows the end-user to override the log file level by
                    specifying a compatible integer in the form of
                    logging.SOMELEVEL (must be upperase)
                    (default: logging.INFO)
    log_filename:   String to represent the log filename (Default: none)
    propagate:      Propagate to root logger
    scope:          A string name for the logger to set it's scope (default: 'root')
    debug_more:     Re-enable extra debug logging from modules like botocore, requests, and urllib3
    formatter:      Allows Adjusting log message format
    """

    # Set scope
    logger = logging.getLogger(scope)
    logger.setLevel(logging.DEBUG)  # Set to DEBUG to capture all messages

    # Clear any existing handlers
    logger.handlers = []

    # True/False propagate logger
    logger.propagate = propagate

    # Create console handler and set level to specified log_level
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)

    # Set console handling formatting
    console_formatter = logging.Formatter(formatter)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    if log_filename:
        # Regular log file handler
        if len(log_filename) < 4 or log_filename[-4:] == ".log":
            this_log_filename = log_filename
        else:
            this_log_filename = log_filename + ".log"

        file_handler = logging.FileHandler(
            this_log_filename, "w", encoding=None, delay="true"
        )
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(formatter)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Debug log file handler
        debug_filename = log_filename.replace(".log", "-debug.log")
        debug_handler = logging.FileHandler(
            debug_filename, "w", encoding=None, delay="true"
        )
        debug_handler.setLevel(logging.DEBUG)  # Always set to DEBUG level
        debug_formatter = logging.Formatter(formatter)
        debug_handler.setFormatter(debug_formatter)
        logger.addHandler(debug_handler)

    logger = logging.LoggerAdapter(logger, {"scope": scope})
    return logger


# Default json library doesn't like to serialize decimal :)
# Convert Decimal objects to strings before serializing to JSON
def decimal_default(obj):
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError("Object of type Decimal is not JSON serializable")


def group_transactions_by_category(transaction_data):
    category_groups = {}

    def amount_to_float(amount_str):
        return float(str(amount_str).replace("$", "").replace(",", ""))

    def format_account(bank, account_info):
        # Extract account number from the account info string
        account_num = account_info.split("#")[1].split(":")[0].strip()
        return f"{bank.upper()} #{account_num}"

    # Process all transactions across all banks and users
    for bank, bank_data in transaction_data.items():
        if bank != "budget":
            for user, user_data in bank_data.items():
                if user_data and "transactions" in user_data:
                    account = format_account(bank, user_data["account"])
                    for transaction in user_data["transactions"]:
                        category = transaction.get(
                            "transaction_category", "uncategorized"
                        )
                        date = transaction["transaction_date"]
                        description = transaction["description"]
                        amount = transaction["amount"]

                        if category not in category_groups:
                            category_groups[category] = []

                        # Format with amount, description, and account
                        formatted_amount = f"{amount:<10}"
                        transaction_str = (
                            f"{date:<8} {formatted_amount} {description:<40} {account}"
                        )
                        category_groups[category].append(transaction_str)

    # Sort transactions within each category by amount
    for category in category_groups:
        category_groups[category] = sorted(
            category_groups[category],
            key=lambda x: amount_to_float(x.split()[1]),
            reverse=True,
        )

    return category_groups


def sort_transactions_by_amount(transaction_data):
    expense_tuples = []

    # Navigate through the nested structure
    for bank, bank_data in transaction_data.items():
        if bank != "budget":  # Skip the budget key
            for user, user_data in bank_data.items():
                if user_data and "transactions" in user_data:
                    for transaction in user_data["transactions"]:
                        expense_tuples.append(
                            (transaction["description"], transaction["amount"])
                        )

    # Convert amount strings to float for sorting
    def amount_to_float(amount_str):
        return float(str(amount_str).replace("$", "").replace(",", ""))

    # Sort by amount (highest to lowest)
    return sorted(expense_tuples, key=lambda x: amount_to_float(x[1]), reverse=True)


def json_to_pdf(data, output_pdf):
    # Convert dictionary to a JSON string
    json_data = json.dumps(data, indent=4)

    # Create a SimpleDocTemplate to build the PDF
    pdf = SimpleDocTemplate(output_pdf, pagesize=letter)
    elements = []

    # Adding a title
    title = "Generated PDF Report"
    elements.append(title)

    # Iterate through the data to structure it nicely
    for section, items in data.items():
        # Section title
        elements.append(f"\n{section}\n{'-'*len(section)}")

        if isinstance(items, dict):
            # Format as table for nested dictionaries
            table_data = [[k, v] for k, v in items.items()]
            table = Table(table_data)
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.gray),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ]
                )
            )
            elements.append(table)
        else:
            # Simple text list
            for key, value in items.items():
                elements.append(f"{key}: {value}")

    # Build the PDF
    pdf.build(elements)
