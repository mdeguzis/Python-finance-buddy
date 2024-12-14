from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

def initialize_logger(log_level=logging.INFO, log_filename=None,
                      propagate=False, scope=None, debug_more=False,
                      formatter="%(asctime)s - %(levelname)s - %(message)s"):
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

    # Only set if the default is not set
    if formatter == "%(asctime)s - %(levelname)s - %(message)s" and log_level == logging.DEBUG:
        print("Formatter not set, and debug mode, using full message details")
        formatter = "[%(name)s] %(asctime)s - %(levelname)s - %(message)s"
    
    # Add the logger name tossing out messages if using debug mode
    # Helpel for sorting out messages and suppressing garbage
    if log_level == logging.DEBUG:
       formatter = f"[%(name)s] {formatter}"

    # Suppress overload of requests library debug messages
    if not debug_more:
        logging.getLogger("botocore").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Set scope
    logger = logging.getLogger(scope)
    logger.setLevel(log_level)

    # True/False propagate logger so that routines with multiple
    # loggers (modules, unittests), do not repeat messages
    # https://docs.python.org/3/library/logging.html#logging.Logger.propagate
    logger.propagate = propagate
 
    # create console handler and set level to info
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)

    # Set console handling formatting
    console_formatter = logging.Formatter(formatter)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    if log_filename != None:
        # create file handler for typical logs
        if len(log_filename) < 4 or log_filename[-4:] == ".log":
            this_log_filename = log_filename
        else:
            this_log_filename = log_filename + ".log"

        # Set file_handler to target level
        file_handler = logging.FileHandler(
            this_log_filename, "w", encoding=None, delay="true")
        file_handler.setLevel(log_level)

        # Set formatting
        file_formatter = logging.Formatter(formatter)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger

# Default json library doesn't like to serialize decimal :)
# Convert Decimal objects to strings before serializing to JSON
def decimal_default(obj):
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError("Object of type Decimal is not JSON serializable")
