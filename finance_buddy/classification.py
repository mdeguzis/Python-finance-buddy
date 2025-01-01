import os
import re
import json
import pickle
import logging
from enum import Enum
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from fuzzywuzzy import fuzz

# Initialize logging
logger = logging.getLogger("cli")

# Constants
DATA_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
PRIVATE_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "private")
MODEL_PATH = os.path.join(DATA_FOLDER, "model.pkl")
VECTORIZER_PATH = os.path.join(DATA_FOLDER, "vectorizer.pkl")


class ExpenseCategory(Enum):
    BILLS = "bills"
    ENTERTAINMENT = "entertainment"
    FOOD = "food"
    GROCERIES = "groceries"
    HEALTH = "health"
    INSURANCE = "insurance"
    MISCELLANEOUS = "miscellaneous"
    OTHER = "other"
    PERSONAL_CARE = "personal care"
    RENT = "rent"
    SERVICES = "services"
    SHOPPING = "shopping"
    SOFTWARE = "software"
    SUBSCRIPTIONS = "subscriptions"
    TRANSPORTATION = "transportation"
    UNKNOWN = "unknown"
    UTILITIES = "utilities"


class TransactionClassifier:
    def __init__(self):
        self.root_dir = os.path.dirname(os.path.dirname(__file__))
        self.data_folder = DATA_FOLDER
        self.private_folder = PRIVATE_FOLDER
        self.model_dir = os.path.expanduser("~/.finance_buddy")

        # Create necessary directories
        for directory in [self.data_folder, self.private_folder, self.model_dir]:
            os.makedirs(directory, exist_ok=True)

        self.model_file = MODEL_PATH
        self.vectorizer_file = VECTORIZER_PATH
        self.training_data_file = os.path.join(DATA_FOLDER, "training-categories.json")

        self.vectorizer = None
        self.model = None

        self.known_patterns = {
            r"GIANT\s*\d*": "groceries",
            r"GONG CHA": "food",
            r"WALMART": "shopping",
            r"TARGET": "shopping",
            r"UBER\s*EATS": "food",
            r"DOORDASH": "food",
            r"NETFLIX": "entertainment",
            r"SPOTIFY": "entertainment",
            r"AMAZON": "shopping",
            r"WHOLEFDS": "groceries",
            r"TRADER\s*JOE": "groceries",
        }

    def _load_model(self):
        """Load the saved model and vectorizer"""
        try:
            if os.path.exists(self.model_file) and os.path.exists(self.vectorizer_file):
                with open(self.model_file, "rb") as f:
                    self.model = pickle.load(f)
                with open(self.vectorizer_file, "rb") as f:
                    self.vectorizer = pickle.load(f)
            else:
                self.train_and_save()
        except Exception as e:
            raise Exception(f"Error loading model: {str(e)}")

    def train_and_save(self):
        """Train a new model and save it"""
        try:
            # Load training data
            training_descriptions, training_categories = self._prepare_training_data()

            if not training_descriptions:
                raise ValueError("No training data available")

            # Create and train the vectorizer
            self.vectorizer = TfidfVectorizer(
                analyzer="word", token_pattern=r"[a-zA-Z0-9]+", stop_words="english"
            )
            X = self.vectorizer.fit_transform(training_descriptions)

            # Create and train the model
            self.model = MultinomialNB()
            self.model.fit(X, training_categories)

            # Save the trained model and vectorizer
            self._save_model()

            logger.info("Successfully trained and saved new model")
            return True

        except Exception as e:
            logger.error(f"Error training model: {str(e)}")
            return False

    def _prepare_training_data(self):
        """Prepare training data from JSON file"""
        training_descriptions = []
        training_categories = []

        try:
            with open(self.training_data_file, "r") as f:
                data = json.load(f)

            if isinstance(data, dict):
                # Dictionary format
                for description, category in data.items():
                    if category.lower() not in (e.value for e in ExpenseCategory):
                        logger.warning(
                            f"Skipping invalid category '{category}' for '{description}'"
                        )
                        continue

                    training_descriptions.append(self.clean_text(description))
                    training_categories.append(category.lower())

                    # Add variations
                    variations = [
                        f"{description} #",
                        f"{description} STORE",
                        f"SQ *{description}",
                        f"{description}*",
                        f"{description} LLC",
                        f"{description} INC",
                    ]

                    for variation in variations:
                        training_descriptions.append(self.clean_text(variation))
                        training_categories.append(category.lower())

            elif isinstance(data, list):
                # List format
                for item in data:
                    if (
                        isinstance(item, dict)
                        and "transaction" in item
                        and "category" in item
                    ):
                        description = item["transaction"]
                        category = item["category"]

                        if category.lower() not in (e.value for e in ExpenseCategory):
                            logger.warning(
                                f"Skipping invalid category '{category}' for '{description}'"
                            )
                            continue

                        training_descriptions.append(self.clean_text(description))
                        training_categories.append(category.lower())

                        # Add variations
                        variations = [
                            f"{description} #",
                            f"{description} STORE",
                            f"SQ *{description}",
                            f"{description}*",
                            f"{description} LLC",
                            f"{description} INC",
                        ]

                        for variation in variations:
                            training_descriptions.append(self.clean_text(variation))
                            training_categories.append(category.lower())

            logger.info(f"Prepared {len(training_descriptions)} training examples")
            return training_descriptions, training_categories

        except Exception as e:
            logger.error(f"Error preparing training data: {str(e)}")
            return [], []

    def _save_model(self):
        """Save the current model and vectorizer"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.model_file), exist_ok=True)
            os.makedirs(os.path.dirname(self.vectorizer_file), exist_ok=True)

            # Save model and vectorizer
            with open(self.model_file, "wb") as f:
                pickle.dump(self.model, f)
            with open(self.vectorizer_file, "wb") as f:
                pickle.dump(self.vectorizer, f)

            logger.info("Saved model and vectorizer successfully")
            return True
        except Exception as e:
            logger.error(f"Error saving model: {str(e)}")
            return False

    def predict_category(self, description, confidence_threshold=0.6):
        """Predict category using multiple matching strategies"""
        if not self.model or not self.vectorizer:
            self._load_model()

        # Keep original description for regex matching
        original_description = description
        training_dict = {}  # Initialize empty dictionary

        # 1. Load and check training data for regex matches
        try:
            with open(self.training_data_file, "r") as f:
                training_data = json.load(f)
                if isinstance(training_data, list):
                    # Convert list format to dictionary
                    training_dict = {
                        item["transaction"]: item["category"]
                        for item in training_data
                        if isinstance(item, dict)
                        and "transaction" in item
                        and "category" in item
                    }
                else:
                    # Assume it's already in dictionary format
                    training_dict = training_data

        except Exception as e:
            logger.warning(f"Could not load training data: {str(e)}")
            training_dict = {}  # Ensure dictionary exists even if load fails

        # 2. Try regex matching
        for pattern, category in training_dict.items():
            try:
                if re.search(pattern, original_description, re.IGNORECASE):
                    logger.debug(f"Regex match found: {pattern} -> {category}")
                    return category, 1.0
            except re.error as e:
                logger.debug(f"Invalid regex pattern '{pattern}': {str(e)}")
                continue

        # 3. ML model prediction as fallback
        try:
            cleaned_description = self.clean_text(original_description)
            desc_vector = self.vectorizer.transform([cleaned_description])
            prediction = self.model.predict(desc_vector)[0]
            probabilities = self.model.predict_proba(desc_vector)[0]
            confidence = max(probabilities)

            logger.debug(f"ML prediction: {prediction} (confidence: {confidence:.2f})")

            if confidence >= confidence_threshold:
                return prediction, confidence
            else:
                return "other", confidence

        except Exception as e:
            logger.error(f"Error in ML prediction: {str(e)}")
            return "other", 0.0

    def categorize_transaction(self, description, vectorizer=None, model=None):
        """
        Main method to categorize a transaction description
        """
        category, _ = self.predict_category(description)
        return category

    def clean_text(self, text):
        """Clean and standardize text for better matching"""
        if not text:
            return ""

        # Convert to uppercase
        text = text.upper()

        # Remove special characters but keep spaces
        text = re.sub(r"[^\w\s]", " ", text)

        # Replace multiple spaces with single space
        text = " ".join(text.split())

        # Remove common transaction suffixes/prefixes
        common_suffixes = [
            r"\s+\d+$",  # Numbers at the end
            r"\s+#\d+$",  # Store numbers
            r"\s+LLC$",
            r"\s+INC$",
            r"\s+CORP$",
            r"\s+USA$",
            r"\s+VA$",
            r"\s+MD$",
            r"\s+DC$",
        ]

        for suffix in common_suffixes:
            text = re.sub(suffix, "", text)

        return text.strip()

    def save_descriptions(self, descriptions_data):
        """
        Save transaction descriptions to JSON file,
        only updating existing entries without adding new ones
        """
        try:
            # Load existing data
            if not os.path.exists(self.training_data_file):
                logger.warning("Training data file does not exist")
                return False

            with open(self.training_data_file, "r") as f:
                existing_data = json.load(f)

            # Track which descriptions were updated
            updates_made = False
            updates_count = 0

            # Only update existing entries
            for desc in descriptions_data:
                if (
                    isinstance(desc, dict)
                    and "transaction" in desc
                    and "category" in desc
                ):
                    transaction = desc["transaction"]
                    category = desc["category"]

                    # Only update if the entry already exists
                    if transaction in existing_data:
                        if (
                            existing_data[transaction] != category
                            and category != "unknown"
                        ):
                            existing_data[transaction] = category
                            updates_made = True
                            updates_count += 1
                            logger.debug(
                                f"Updated category for '{transaction}' to '{category}'"
                            )
                    else:
                        logger.debug(f"Skipping new transaction: {transaction}")

            # Only save if updates were made
            if updates_made:
                with open(self.training_data_file, "w") as f:
                    json.dump(existing_data, f, indent=4, sort_keys=True)
                logger.info(
                    f"Updated {updates_count} existing descriptions in {self.training_data_file}"
                )
            else:
                logger.info("No updates needed for existing descriptions")

            return True

        except Exception as e:
            logger.error(f"Error saving descriptions: {str(e)}")
            return False


# Create global instance
classifier = TransactionClassifier()


# Keep existing functions but modify them to use the classifier instance
def generate_categories():
    return [category.value for category in ExpenseCategory]


def clean_text(text):
    return classifier.clean_text(text)


def load_training_data():
    """Load training data with variations"""
    training_descriptions = []
    training_categories = []

    with open(os.path.join(DATA_FOLDER, "training-categories.json"), "r") as f:
        training_data = json.load(f)

    for merchant, category in training_data.items():
        if category.lower() not in (e.value for e in ExpenseCategory):
            logger.error(f"Invalid category '{category}' for merchant '{merchant}'!")
            exit(1)

        training_descriptions.append(merchant)
        training_categories.append(category)

        variations = [
            f"{merchant} #",
            f"{merchant} STORE",
            f"SQ *{merchant}",
            f"{merchant}*",
            f"{merchant} LLC",
            f"{merchant} INC",
        ]

        for variation in variations:
            training_descriptions.append(variation)
            training_categories.append(category)

    return training_descriptions, training_categories


def get_model():
    """Legacy function for backwards compatibility"""
    if not classifier.model or not classifier.vectorizer:
        classifier._load_model()
    return classifier.vectorizer, classifier.model


def save_model(
    vectorizer, model, vectorizer_path=VECTORIZER_PATH, model_path=MODEL_PATH
):
    with open(vectorizer_path, "wb") as f:
        pickle.dump(vectorizer, f)
        logger.info(f"Saved vector model to {vectorizer_path}")
    with open(model_path, "wb") as f:
        pickle.dump(model, f)
        logger.info(f"Saved model to {model_path}")


def load_model(vectorizer_path=VECTORIZER_PATH, model_path=MODEL_PATH):
    with open(vectorizer_path, "rb") as f:
        vectorizer = pickle.load(f)
    with open(model_path, "rb") as f:
        model = pickle.load(f)
    return vectorizer, model


def test_predictions():
    """Test the model's predictions"""
    vectorizer, model = get_model()

    if not vectorizer or not model:
        logger.error("Could not load model. Please train first.")
        return

    descriptions = [
        "CHIPOTLE USAPAVAFL",
        "PRT CRYSTAL 702-9205600VA",
        "SQ *CAFE AMAZONSomethingUSA",
        "GOOGLE *CBS Mobile",
    ]

    print("=" * 79)
    print("Making predictions on sample data...")
    print("=" * 79)

    unknowns = []
    for description in descriptions:
        print(f"\nAttempting to predict category for: {description}")
        category = categorize_transaction(description)
        print(f"Predicted category: {category}")
        if category == "unknown" or category == "other":
            unknowns.append([description, category])

    if unknowns:
        print("\n" + "=" * 79)
        print("Low confidence / unknowns:")
        print("=" * 79)
        for unknown in unknowns:
            print(unknown)


def save_descriptions(file_path, descriptions):
    """
    Module-level function to save descriptions
    Maintains compatibility with existing code
    """
    # Ignore file_path parameter as we're using the configured path in the classifier
    return classifier.save_descriptions(descriptions)


def predict_category(description):
    """Module-level function to predict category with confidence"""
    return classifier.predict_category(description)


def categorize_transaction(description, vectorizer=None, model=None):
    """
    Module-level function that supports both old and new style calls
    """
    if vectorizer is not None and model is not None:
        # Old style - use provided vectorizer and model
        try:
            desc_vector = vectorizer.transform([clean_text(description)])
            prediction = model.predict(desc_vector)[0]
            return prediction
        except Exception as e:
            logger.error(f"Error in old-style categorization: {str(e)}")
            return "other"
    else:
        # New style - use classifier instance
        return classifier.categorize_transaction(description)


def train_and_save():
    """Module-level function to train and save the model"""
    return classifier.train_and_save()
