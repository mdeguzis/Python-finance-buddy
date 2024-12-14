#!/usr/bin/env python

import argparse
import json
import logging

from pathlib import Path
from enum import Enum

from finance_buddy import capital_one
from finance_buddy import utils

# Initialize
logger = logging.getLogger(__name__)
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
    logger.info("Starting main")
    args = process_args()
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

    # Print data
    if args.print:
        logger.info(
            json.dumps(transaction_data, indent=4, default=utils.decimal_default)
        )

    ## Add high level info for budgeting
    # transaction_data["budget"] = {}
    # transaction_data["budget"]["breakdown"] = {}

    ## Capital one budget information
    # transaction_data["budget"]["breakdown"]["capital_one"] = {}
    # transaction_data["budget"]["breakdown"]["capital_one"]
    # for user, value in transaction_data["capital_one"].items():
    #    if value:
    #        total_expenses = value["transactions_total_amount"]
    #        transaction_data["budget"]["breakdown"]["capital_one"][user] = {}
    #        transaction_data["budget"]["breakdown"]["capital_one"][user][
    #            "expenses"
    #        ] = total_expenses

    # Sort main keys so "budget" key is on top
    sorted_data = {key: transaction_data[key] for key in sorted(transaction_data)}

    # Write report
    with open(report_filename, "w") as outfile:
        json.dump(sorted_data, outfile, indent=4, default=utils.decimal_default)


if __name__ == "__main__":
    args = process_args()
    if args.debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Add console handler to logger
    logger.addHandler(console_handler)

    # File handler
    file_handler = logging.FileHandler(log_filename, mode="w")
    file_handler.setFormatter(formatter)
    # Add file handler to logger
    logger.addHandler(file_handler)

    main()

    print(f"Log: {log_filename}")
    print(f"Transactions report: {report_filename}")
