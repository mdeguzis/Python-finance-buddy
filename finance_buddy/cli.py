#!/usr/bin/env python

import argparse
import json
import logging

from pathlib import Path
from enum import Enum

from finance_buddy import capital_one
from finance_buddy import classification
from finance_buddy import utils

# Initialize
report_filename = "/tmp/monthly-budget-report.json"
log_filename = "/tmp/monthly-budget.log"


def process_args():
    parser = argparse.ArgumentParser(description="Analyze financial statements.")
    parser.add_argument(
        "--capital-one",
        "-c",
        help="Path to the Capital One statement (CSV or PDF).",
    )
    parser.add_argument(
        "--debug", "-d", action="store_true", help="Enable debug output"
    )
    parser.add_argument(
        "--print", "-p", action="store_true", help="Print all data to screen"
    )
    return parser.parse_args()


def main():
    """Entry point for the application."""
    args = process_args()
    log_level = logging.DEBUG if args.debug else logging.INFO

    # Initialize logger
    logger = utils.initialize_logger(log_level=log_level, log_filename=log_filename, scope="cli")

    # Check the file extension
    transaction_data = {}
    data = None
    if args.capital_one:
        file_path = Path(args.capital_one).resolve()
        logger.info(f"Analyzing file: {file_path}")
        if file_path.suffix.lower() == ".csv":
            logger.info("Detected file type: CSV")
            data = capital_one.analyze_capitalone_csv(file_path)
        elif file_path.suffix.lower() == ".pdf":
            logger.info("Detected file type: PDF")
            data = capital_one.analyze_capitalone_pdf(file_path)
        else:
            logger.error("Unsupported file type. Please provide a CSV or PDF file.")
        transaction_data["capital_one"] = data
    else:
        logger.error("No file provided. Please provide file(s) to analyze")
        exit(1)

    # Print data
    if args.print:
        logger.info(
            json.dumps(transaction_data, indent=4, default=utils.decimal_default)
        )

    ## Add high level info for budgeting
    transaction_data["budget"] = {}
    transaction_data["budget"]["breakdown"] = {}

    # Write the descriptions to the "data" folder
    # This is to help with categorization
    # Only write if it doesn't exist
    descriptions_path = Path("private/descriptions-data.json")
    descriptions_path = descriptions_path.resolve()
    descriptions = []

    # Get descriptions by searching all of transaction_data for the "description" key
    # In cli.py
    # First, load existing descriptions to preserve categories
    existing_descriptions = []
    if descriptions_path.exists():
        try:
            with open(descriptions_path, "r", encoding="utf-8") as f:
                existing_descriptions = json.load(f)
        except json.JSONDecodeError:
            logger.warning("Could not load existing descriptions file")

    # Create a dictionary for quick lookup of existing categories
    existing_categories = {
        d.get("transaction", d.get("description")): d.get("category")
        for d in existing_descriptions
    }

    # Get descriptions by searching all of transaction_data for the "description" key
    descriptions = []
    for bank, bank_data in transaction_data.items():
        for user, user_data in bank_data.items():
            if user_data:
                for transaction in user_data["transactions"]:
                    desc = transaction["description"]
                    if desc not in [d.get("transaction", d.get("description")) for d in descriptions]:
                        descriptions.append({
                            "transaction": desc,
                            "category": existing_categories.get(desc, "unknown")  # Use existing category if available
                        })

    classification.save_descriptions(descriptions_path, descriptions)

    # Capital one budget information
    try:
        transaction_data["budget"]["breakdown"]["capital_one"] = {}
        for user, value in transaction_data["capital_one"].items():
            if value:
                total_expenses = value["transactions_total_amount"]
                transaction_data["budget"]["breakdown"]["capital_one"][user] = {}
                transaction_data["budget"]["breakdown"]["capital_one"][user][
                "expenses"
            ] = total_expenses
    except TypeError as e:
        raise Exception(f"Error processing Capital One data: {e}")

    # Sort main keys so "budget" key is on top
    sorted_data = {key: transaction_data[key] for key in sorted(transaction_data)}

    # Write report
    with open(report_filename, "w") as outfile:
        json.dump(sorted_data, outfile, indent=4, default=utils.decimal_default)

    logger.info(f"Log: {log_filename}")
    logger.info(f"Transactions report: {report_filename}")
    logger.info("Descriptions written to %s", descriptions_path)

if __name__ == "__main__":
    main()
