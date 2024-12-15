from decimal import Decimal
import re

import locale
import logging
import pandas as pd
import pdfplumber

# Get a child logger that inherits from the root logger
logger = logging.getLogger('cli')

locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

from finance_buddy import classification

def analyze_capitalone_csv(file_path):
    try:
        # Load and analyze the CSV file
        data = pd.read_csv(file_path)
        print("\nCapital One CSV Headers:")
        print(data.columns.tolist())
        print("\nFirst Row of Data:")
        print(data.iloc[-2].to_dict())  # Display the first row for analysis
    except Exception as e:
        print(f"Error reading the CSV file: {e}")

    return data

def analyze_capitalone_pdf(file_path, accumulated_data=None):
    parsed_data = accumulated_data or {}

    try:
        current_page = 0
        with pdfplumber.open(file_path) as pdf:
            logger.info("Extracting data from Capital One PDF...")
            for page_num, page in enumerate(pdf.pages):
                current_page += 1
                logger.info("Processing page %s...", current_page)
                # Extract text to locate "Transactions" section
                page_text = page.extract_text()
                parsed_data = parse_capitalone_transactions_text(
                    page_text, parsed_data, current_page
                )
        if parsed_data:
            return parsed_data
        else:
            logger.error("Failed to parse data! Data is empty!")
            exit(1)
    except Exception as e:
        raise Exception(e)


def parse_capitalone_transactions_text(pdf_text, data, page_num):
    """
    Parse the PDF text to extract and organize transaction data.
    """
    lines = pdf_text.splitlines()
    current_name = None
    current_account = None
    have_continuation = False
    transaction_ct = -2

    name_pattern = re.compile(r"^([A-Z\s]+) #(\d+): Transactions")
    user_transactions_done = re.compile(
        r"^([A-Z\s]+) #(\d+): Total Transactions (\$\d+(?:,\d{3})*\.\d{2})"
    )

    # Match any variation of money + expected pattern
    # Example: 'Nov 3 Nov 8 Moble Payment - ABCD $0,000.00"
    # Example: 'Nov 20 Nov 22 Moble Payment (new) - ABCD $0.00"
    transaction_pattern = re.compile(
        r"(\w{3} \d{1,2}) (\w{3} \d{1,2}) ([\w\s\*]+.*?[a-zA-Z]) (\$\d{1,3}(?:,\d{3})*(?:\.\d{1,2}))"
    )
    header = "Trans Date Post Date Description Amount"
    processing_transactions = False

    for line in lines:
        # Fetch current user from queue memory
        # Regex matching
        if data.get("current_queue", ""):
            current_name = data["current_queue"]
        name_match = name_pattern.match(line)
        done_match = user_transactions_done.match(line)

        # If we hit "<NAME> #<ACCOUNT>: Total Transactions", we are done for the current user
        # if done_match and not processing_transactions:
        # Check this early, as if we trigger done too early, we'll notice discrepancies
        if done_match:
            this_user = done_match.group(1)
            if have_continuation:
                logger.error(
                    "We should still be processing transactions. Something went wrong..."
                )
                exit(1)
            # error check total if not 0
            if data[this_user]["transactions_total_amount"] == 0:
                logger.error("Total amount is 0. Something went wrong...")
                exit(1)
            logger.info("Done processing transactions for '%s'", this_user)
            # Our total
            total_amount_from_data = data[this_user]["transactions_total_amount"]
            logger.debug("Converting our total %s to Decimal", total_amount_from_data)
            total_amount_processed = locale.currency(Decimal(total_amount_from_data), grouping=True)
            # Statement total
            statement_final = done_match.group(3).replace("$", "").replace(",", "")
            logger.debug(
                "Converting statement final total %s, to Decimal", statement_final)
            statement_final_amount = locale.currency(Decimal(statement_final), grouping=True)
            # Verify
            if total_amount_processed != statement_final_amount:
                logger.error(
                    "Failed to verify transaction amounts against process amount!"
                )
                logger.error("Found: %s", total_amount_processed)
                logger.error("Reported by document: %s", statement_final_amount)
                exit(1)
            logger.info("Final amount verified!")
            data[this_user]["verified_amounts"] = True

            # Error if our current total amount processed doesn't match the amount reported in the final line
            # Clear the queue
            data["current_queue"] = None
            processing_transactions = False
            break

        # Get current person we are handling
        if name_match:
            current_name = name_match.group(1)
            current_account = name_match.group(0)
            # Set name in the queue so we have it handy
            data["current_queue"] = current_name
            logger.info(
                "Processing transactions for '%s' (Account #%s)", 
                current_name, current_account
            )

            # Initialize if we don't have data yet
            if current_name not in data:
                data[current_name] = {}
                data[current_name]["account"] = current_account

            if not data.get(current_name, "").get("verified_amounts", ""):
                data[current_name]["verified_amounts"] = False
            if not data.get(current_name, "").get("transactions_count", ""):
                data[current_name]["transactions_count"] = []
            if not data.get(current_name, "").get("transactions", ""):
                data[current_name]["transactions"] = []
            if not data.get(current_name, "").get("transactions_total_amount", ""):
                data[current_name]["transactions_total_amount"] = Decimal(0)
            processing_transactions = False

        elif "Transactions (Continued)" in line:
            logger.info(
                "We have more transactions on page %s: (Continuation found)", page_num
            )
            processing_transactions = True
            have_continuation = True
            continue

        elif line == header and current_name:
            processing_transactions = True
            have_continuation = False
            # Do we have a transactions header and are we processing a user?
            logger.debug("Got transactions on page %s", page_num)
            if not data.get(current_name, "").get("transactions", ""):
                data[current_name]["transactions"] = []
            continue

        elif current_name and processing_transactions:
            # Do we have an active queue and should process transactions?
            # Header: "'Trans Date' 'Post Date' 'Description' 'Amount'"
            have_continuation = False
            try:
                data_match = transaction_pattern.match(line)
                if not data_match:
                    logger.debug("Discarding possible transaction line: %s", line)
                transactions_data_raw = line
                logger.debug("Transaction data (raw): '%s'", transactions_data_raw)
                if data_match:
                    processing_transactions = True
                    transaction_ct += 1
                    data[current_name]["transactions_count"] = transaction_ct
                    logger.debug(data_match.groups())
                    transaction_date = data_match.group(1)
                    post_date = data_match.group(2)
                    description = data_match.group(3)
                    # Attempt to predict category based on training model
                    vectorizer, model = classification.get_model()
                    category = classification.categorize_transaction(description, vectorizer, model)

                    # Move to debug
                    logger.info("Predicted %s for description '%s'", category, description)

                    amount = data_match.group(4).replace("$", "")
                    amount_decimal = Decimal(amount.replace(",", ""))
                    data[current_name]["transactions"].append(
                        {
                            "transaction_date": transaction_date,
                            "transaction_category": category,
                            "post_date": post_date,
                            "description": description,
                            "amount": locale.currency(amount_decimal, grouping=True),
                        }
                    )
                    # Ensure that all the transactions we collect match up later to
                    # the total amount
                    logger.debug("Converting %s to Decimal", amount)
                    logger.debug("Adding %s to total", amount_decimal)
                    data[current_name]["transactions_total_amount"] += amount_decimal
                    total = locale.currency(data[current_name]["transactions_total_amount"], grouping=True)
                    logger.debug("Total: %s", total)
            except Exception as e:
                raise Exception(e)

    return data
