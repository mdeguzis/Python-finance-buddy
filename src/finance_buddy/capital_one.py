import datetime
import locale
import logging
import os
import re
import time

import pandas as pd
import pdfplumber

if os.name == "nt":
    import msvcrt
else:
    msvcrt = None

from decimal import Decimal
from getpass import getpass

from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from finance_buddy import classification

# Get a child logger that inherits from the root logger
logger = logging.getLogger("cli")

locale.setlocale(locale.LC_ALL, "en_US.UTF-8")


def get_password_with_asterisks():
    """Get password with asterisk masking, works on Windows and Unix-like systems"""
    password = []

    while True:
        # Handle Windows systems
        if os.name == "nt":
            char = msvcrt.getwch()
            # Handle backspace
            if char == "\b":
                if password:
                    password.pop()
                    # Remove last asterisk
                    sys.stdout.write("\b \b")
            # Handle enter/return key
            elif char == "\r":
                sys.stdout.write("\n")
                break
            else:
                password.append(char)
                sys.stdout.write("*")
        # Handle Unix-like systems
        else:
            import termios
            import tty

            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                char = sys.stdin.read(1)
                # Handle backspace
                if char == "\x7f":
                    if password:
                        password.pop()
                        sys.stdout.write("\b \b")
                # Handle enter/return key
                elif char == "\r":
                    sys.stdout.write("\n")
                    break
                else:
                    password.append(char)
                    sys.stdout.write("*")
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

        sys.stdout.flush()

    return "".join(password)


def list_accounts(driver):
    """
    List all accounts found on the page with their names and numbers
    """
    logger.debug("\nScanning for accounts...")
    wait = WebDriverWait(driver, 20)
    accounts_found = []

    try:
        logger.debug("\nFound accounts:")
        logger.debug("-" * 50)

        # Look for card images with alt text (credit cards)
        images = driver.find_elements(By.TAG_NAME, "img")
        for img in images:
            alt_text = img.get_attribute("alt")
            if alt_text:  # Only process images with alt text
                try:
                    account_div = img.find_element(
                        By.XPATH,
                        "./ancestor::*[contains(@class, 'primary-detail')]//div[contains(@class, 'account-number')]",
                    )
                    account_number = account_div.text.strip()
                    logger.debug(f"Credit Card: {alt_text}")
                    logger.debug(f"Account: {account_number}")
                    logger.debug("-" * 50)
                    accounts_found.append(("Credit Card", alt_text, account_number))
                except Exception as e:
                    continue

        # Look for savings/checking accounts (spans with ng-tns- class)
        spans = driver.find_elements(By.CSS_SELECTOR, "span[class*='ng-tns-']")
        for span in spans:
            try:
                if span.get_attribute("role") == "heading":
                    account_name = span.text.strip()
                    if account_name:  # Only process if we have a name
                        # Find the associated account number
                        try:
                            account_div = span.find_element(
                                By.XPATH,
                                "./ancestor::*[contains(@class, 'primary-detail')]//div[contains(@class, 'account-number')]",
                            )
                            account_number = account_div.text.strip()
                            logger.debug(f"Bank Account: {account_name}")
                            logger.debug(f"Account: {account_number}")
                            logger.debug("-" * 50)
                            accounts_found.append(
                                ("Bank Account", account_name, account_number)
                            )
                        except Exception as e:
                            logger.debug(f"Bank Account: {account_name}")
                            logger.debug("Account: [No number found]")
                            logger.debug("-" * 50)
                            accounts_found.append(("Bank Account", account_name, "N/A"))
            except Exception as e:
                continue

        if not accounts_found:
            logger.debug("No accounts found!")
            exit(2)

        return accounts_found

    except Exception as e:
        logger.debug(f"Error scanning accounts: {str(e)}")
        return []


def list_and_select_account(driver):
    """
    List all accounts and let user select one
    Returns the selected account element
    """
    logger.debug("\nScanning for accounts...")
    wait = WebDriverWait(driver, 20)
    accounts_found = []

    try:
        # Look for card images with alt text (credit cards)
        images = driver.find_elements(By.TAG_NAME, "img")
        for img in images:
            alt_text = img.get_attribute("alt")
            if alt_text:  # Only process images with alt text
                try:
                    account_div = img.find_element(
                        By.XPATH,
                        "./ancestor::*[contains(@class, 'primary-detail')]//div[contains(@class, 'account-number')]",
                    )
                    account_number = account_div.text.strip()
                    account_element = img.find_element(
                        By.XPATH, "./ancestor::*[contains(@class, 'primary-detail')]"
                    )
                    accounts_found.append(
                        ("Credit Card", alt_text, account_number, account_element)
                    )
                except Exception as e:
                    continue

        # Look for savings/checking accounts
        spans = driver.find_elements(By.CSS_SELECTOR, "span[class*='ng-tns-']")
        for span in spans:
            try:
                if span.get_attribute("role") == "heading":
                    account_name = span.text.strip()
                    if account_name:
                        try:
                            account_div = span.find_element(
                                By.XPATH,
                                "./ancestor::*[contains(@class, 'primary-detail')]//div[contains(@class, 'account-number')]",
                            )
                            account_number = account_div.text.strip()
                            account_element = span.find_element(
                                By.XPATH,
                                "./ancestor::*[contains(@class, 'primary-detail')]",
                            )
                            accounts_found.append(
                                (
                                    "Bank Account",
                                    account_name,
                                    account_number,
                                    account_element,
                                )
                            )
                        except Exception as e:
                            accounts_found.append(
                                ("Bank Account", account_name, "N/A", span)
                            )
            except Exception as e:
                continue

        if not accounts_found:
            logger.debug("No accounts found!")
            return None

        # Display accounts and get user selection
        logger.debug("\nAvailable accounts:")
        for idx, (acc_type, acc_name, acc_num, _) in enumerate(accounts_found, 1):
            if acc_num != "N/A":
                print(f"{idx}. {acc_type}: {acc_name} ({acc_num})")
            else:
                print(f"{idx}. {acc_type}: {acc_name}")

        while True:
            try:
                selection = int(
                    input(
                        "\nEnter the number of the account to access (1-{}): ".format(
                            len(accounts_found)
                        )
                    )
                )
                if 1 <= selection <= len(accounts_found):
                    return accounts_found[selection - 1]
                else:
                    logger.debug("Invalid selection. Please try again.")
            except ValueError:
                logger.debug("Please enter a valid number.")

    except Exception as e:
        logger.debug(f"Error scanning accounts: {str(e)}")
        return None


def click_account(driver, acc_name, acc_number):
    """
    Click on the specific account tile
    """
    wait = WebDriverWait(driver, 20)
    try:
        logger.debug(f"Looking for account tile for {acc_name}...")

        # Try to find by account number first (more specific)
        account_number_clean = acc_number.replace("...", "").strip()
        tiles = driver.find_elements(By.CSS_SELECTOR, "div.account-tile")

        for tile in tiles:
            try:
                # Check if this tile contains our account number
                number_element = tile.find_element(
                    By.CSS_SELECTOR, "div.primary-detail__identity__account-number"
                )
                if account_number_clean in number_element.text:
                    logger.debug(f"Found matching tile for account {acc_name}")

                    # Find and click the View Account button within this tile
                    view_button = tile.find_element(
                        By.CSS_SELECTOR, "button[data-testid^='summary-']"
                    )
                    driver.execute_script(
                        "arguments[0].scrollIntoView(true);", view_button
                    )
                    time.sleep(1)
                    try:
                        view_button.click()
                        logger.debug("Clicked View Account button")
                        return True
                    except:
                        driver.execute_script("arguments[0].click();", view_button)
                        logger.debug("Clicked View Account button using JavaScript")
                        return True
            except Exception as e:
                continue

        logger.debug(f"Could not find account tile for {acc_name}")
        return False

    except Exception as e:
        logger.debug(f"Error clicking account: {str(e)}")
        return False


def login_capital_one(args):
    logger.info("Starting login process for Capital One...")

    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")

    # Add download preferences
    chrome_options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": os.path.expanduser("~/Downloads"),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        },
    )

    # Wait up to 5 minutes to complete a login
    timeout = 60 * 5
    driver = webdriver.Chrome(options=chrome_options)
    # Initialize WebDriverWait right after creating the driver
    wait = WebDriverWait(driver, timeout)
    # Set page load timeout
    driver.set_page_load_timeout(timeout)
    logger.debug("WebDriver initialized")

    try:
        logger.debug("Navigating to login page...")
        driver.get("https://verified.capitalone.com/auth/signin")

        logger.debug("Please log in manually in the browser window.")
        logger.debug("Waiting for login completion and account page to load...")

        # Wait for URL change to indicate successful login
        wait.until(lambda driver: "accountSummary" in driver.current_url)
        logger.debug("Login detected!")

        # After initial page load, minimize or move window off-screen
        try:
            # Minimize the window
            if not args.debug:
                driver.minimize_window()
                logger.debug("Browser window minimized")
        except Exception as e:
            logger.debug(f"Could not minimize window: {str(e)}")

        # Wait for page to load completely
        time.sleep(5)

        # List accounts and get user selection
        selected_account = list_and_select_account(driver)

        if selected_account:
            acc_type, acc_name, acc_num, _ = selected_account
            logger.debug(f"\nSelected: {acc_type}: {acc_name}")

            # Create new headless browser session
            logger.debug("\nInitializing headless browser for automation...")
            chrome_options.add_argument("--headless")
            new_driver = webdriver.Chrome(options=chrome_options)

            # Copy cookies from visible session to headless session
            if not args.debug:
                logger.debug("Transferring session...")
                current_url = driver.current_url
                new_driver.get(current_url)

                cookies = driver.get_cookies()
                for cookie in cookies:
                    if "domain" in cookie and cookie["domain"].startswith("."):
                        cookie["domain"] = cookie["domain"][1:]
                    try:
                        new_driver.add_cookie(cookie)
                    except Exception as e:
                        logger.debug(
                            f"Warning: Could not transfer cookie {cookie.get('name')}: {str(e)}"
                        )

                    driver.quit()
                    driver = new_driver
                    wait = WebDriverWait(driver, 20)

                    logger.debug("Navigating to account page...")
                    driver.refresh()
                    time.sleep(3)

            # Click on the selected account using the new method
            if not click_account(driver, acc_name, acc_num):
                raise Exception("Failed to click on account tile")

            time.sleep(3)  # Wait for account page to load

            # Download statement
            try:
                logger.debug("Attempting to download statement")
                download_statement(driver)
                downloaded_file = wait_for_download(os.path.expanduser("~/Downloads"))
                if downloaded_file:
                    logger.debug(f"Successfully downloaded to: {downloaded_file}")
                    # Rename the file to include current month name and YYYY
                    current_month = datetime.datetime.now().strftime("%B")
                    current_year = datetime.datetime.now().strftime("%Y")
                    new_file_name = (
                        f"capital_one_{acc_name}_{current_month}_{current_year}.pdf"
                    )
                    new_file_path = os.path.join(
                        os.path.expanduser("~/Downloads"), new_file_name
                    )
                    logger.debug(f"Renaming {downloaded_file} to {new_file_name}")
                    os.rename(downloaded_file, new_file_path)
                    logger.info(f"File saved to: {new_file_path}")
                    return new_file_path
                else:
                    logger.error("Download failed - no file found")
                    return None
            except Exception as e:
                logger.error(f"Error during download: {str(e)}")
                return None

        else:
            logger.debug("No account was selected.")

    except Exception as e:
        logger.debug(f"\nERROR: {str(e)}")
        logger.debug(f"Current URL: {driver.current_url}")
        input("Press Enter to exit...")
    finally:
        if "driver" in locals():
            driver.quit()
        logger.debug("Browser closed")


def download_statement(driver):
    """
    Navigate to statements page and download the latest statement
    """
    logger.debug("Navigating to statements page...")

    wait = WebDriverWait(driver, 20)
    try:
        # Click "View Statements" link using the specific data-e2e attribute
        logger.debug("Looking for View Statements link...")
        statements_link = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "[data-e2e='extensibility-bar-link-1']")
            )
        )
        logger.debug("Clicking View Statements...")
        statements_link.click()
        time.sleep(3)

        # Look for the specific Download button - refine the selector to avoid confusion with Zoom
        logger.debug("Looking for Download link...")
        download_link = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//span[text()='Download']"))
        )

        # Debug the download link state
        logger.debug(
            "Download link details: %s", download_link.get_attribute("outerHTML")
        )
        logger.debug("Download link is displayed: %s", download_link.is_displayed())
        logger.debug("Download link is enabled: %s", download_link.is_enabled())

        if not download_link.is_displayed() or not download_link.is_enabled():
            logger.error("Download link is not interactable.")
            raise Exception("Download link is not interactable.")

        # Try regular click first, fallback to JavaScript click if needed
        try:
            logger.debug("Clicking Download button")
            download_link.click()
        except ElementClickInterceptedException as e:
            logger.error(f"Click was intercepted: {e}")
            driver.execute_script("arguments[0].click();", download_link)
        except ElementNotInteractableException as e:
            logger.error(f"Element not interactable: {e}")
            driver.execute_script("arguments[0].click();", download_link)
        except Exception as e:
            logger.error(f"Unexpected error during click: {e}")
            raise

        logger.debug("Statement download initiated")

        # Wait for download to complete (adjust time if needed)
        time.sleep(5)

    except Exception as e:
        logger.error(f"Error during statement download: {e}")
        raise


def wait_for_download(download_dir, timeout=60):
    """
    Wait for the download to complete and return the file path
    """
    logger.debug(f"Waiting for download in directory: {download_dir}")
    start_time = time.time()

    while time.time() - start_time < timeout:
        # Check for both complete and in-progress downloads
        files = os.listdir(download_dir)
        pdf_files = [f for f in files if f.endswith(".pdf")]
        crdownload_files = [f for f in files if f.endswith(".crdownload")]

        # Log the current state
        if crdownload_files:
            logger.debug(f"Download in progress: {crdownload_files[0]}")

        # If we have PDF files and no .crdownload files, download is complete
        if pdf_files and not crdownload_files:
            newest_file = max(
                [os.path.join(download_dir, f) for f in pdf_files], key=os.path.getmtime
            )

            # Verify file is not empty and is accessible
            if os.path.exists(newest_file) and os.path.getsize(newest_file) > 0:
                logger.debug(f"Download completed: {newest_file}")
                # Add a small delay to ensure file is fully written
                time.sleep(2)
                return newest_file

        time.sleep(1)  # Check every second

    raise Exception(f"Download timeout exceeded after {timeout} seconds")


def analyze_capitalone_csv(file_path):
    try:
        # Load and analyze the CSV file
        data = pd.read_csv(file_path)
        logger.debug("\nCapital One CSV Headers:")
        logger.debug(data.columns.tolist())
        logger.debug("\nFirst Row of Data:")
        logger.debug(data.iloc[-2].to_dict())  # Display the first row for analysis
    except Exception as e:
        logger.debug(f"Error reading the CSV file: {e}")

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
            total_amount_processed = locale.currency(
                Decimal(total_amount_from_data), grouping=True
            )
            # Statement total
            statement_final = done_match.group(3).replace("$", "").replace(",", "")
            logger.debug(
                "Converting statement final total %s, to Decimal", statement_final
            )
            statement_final_amount = locale.currency(
                Decimal(statement_final), grouping=True
            )
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
                current_name,
                current_account,
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
                    category = classification.categorize_transaction(description)
                    logger.debug(
                        "Predicted %s for description '%s'", category, description
                    )

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
                    total = locale.currency(
                        data[current_name]["transactions_total_amount"], grouping=True
                    )
                    logger.debug("Total: %s", total)
            except Exception as e:
                raise Exception(e)

    return data
