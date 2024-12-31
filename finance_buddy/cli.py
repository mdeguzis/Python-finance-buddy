#!/usr/bin/env python

import argparse
import json
import locale
import logging

from pathlib import Path
from enum import Enum

from finance_buddy import capital_one
from finance_buddy import classification
from finance_buddy import utils
from decimal import Decimal

# Initialize
report_filename = "/tmp/finance-buddy-report.json"
log_filename = "/tmp/finance-buddy.log"


def process_args():
    parser = argparse.ArgumentParser(description="Analyze financial statements.")
    parser.add_argument(
        "--capital-one",
        "-c",
        action="store_true",
        help="Automatically download and analyze latest Capital One statement",
    )
    parser.add_argument(
        "--capital-one-file",
        "-cf",
        help="Path to the Capital One statement (CSV or PDF).",
    )
    parser.add_argument(
        "--train", action="store_true", help="Train and save the model.", default=False
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test predictions using the model.",
        default=False,
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
    transaction_data = {}
    data = None
    locale.setlocale(locale.LC_ALL, "en_US.UTF-8")

    # Initialize logger
    logger = utils.initialize_logger(
        log_level=log_level, log_filename=log_filename, scope="cli"
    )

    # Login to capital one and get PDF location
    pdf_location = capital_one.login_capital_one(args)
    if pdf_location:
        logger.info(f"Successfully downloaded statement to: {pdf_location}")
        args.capital_one_file = pdf_location
    else:
        logger.error("Failed to download Capital One statement")
        exit(1)

    if args.train:
        classification.train_and_save()
    if args.test:
        classification.test_predictions()

    # Check the file extension
    if not args.train and not args.test:
        if args.capital_one:
            file_path = Path(args.capital_one_file).resolve()
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
                        if desc not in [
                            d.get("transaction", d.get("description"))
                            for d in descriptions
                        ]:
                            descriptions.append(
                                {
                                    "transaction": desc,
                                    "category": existing_categories.get(
                                        desc, "unknown"
                                    ),  # Use existing category if available
                                }
                            )

        classification.save_descriptions(descriptions_path, descriptions)

        # Bank breakdown by user
        banks = ["capital_one", "chase"]
        budget_total_expenses = 0
        try:
            transaction_data["budget"]["breakdown"]["by-bank"] = {}
            transaction_data["budget"]["breakdown"]["expenses_breakdown"] = {}
            for bank in banks:
                if transaction_data.get(bank):
                    transaction_data["budget"]["breakdown"]["by-bank"][bank] = {}
                    for user, value in transaction_data[bank].items():
                        if value:
                            total_expenses = value["transactions_total_amount"]
                            budget_total_expenses += total_expenses
                            transaction_data["budget"]["breakdown"]["by-bank"][bank][
                                user
                            ] = {}
                            transaction_data["budget"]["breakdown"]["by-bank"][bank][
                                user
                            ]["expenses"] = locale.currency(
                                total_expenses, grouping=True
                            )
                            "expenses"

                            # Create a subset of data for just the current user
                            user_transactions = {bank: {user: value}}
                            # Pass only the current user's transactions
                            transaction_data["budget"]["breakdown"][
                                "expenses_breakdown"
                            ][user] = []
                            transaction_data["budget"]["breakdown"][
                                "expenses_breakdown"
                            ][user] = utils.group_transactions_by_category(
                                user_transactions
                            )

            # High level non-user
            # Format budget_total_expenses as currency
            transaction_data["budget"]["breakdown"]["total_expenses"] = locale.currency(
                budget_total_expenses, grouping=True
            )
        except TypeError as e:
            transaction_data["budget"]["breakdown"]["total_expenses"] = locale.currency(
                budget_total_expenses, grouping=True
            )
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
