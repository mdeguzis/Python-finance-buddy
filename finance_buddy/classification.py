import logging
import pickle
import json
import os
import re
from rapidfuzz import fuzz
from enum import Enum

from fuzzywuzzy import fuzz
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB

# Initialize logging
logger = logging.getLogger(__name__)

# Constants
# Get absolute path to project root folder (one level up from current file)
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_FOLDER = os.path.join(ROOT_DIR, "data")
PRIVATE_DATA_FOLDER = os.path.join(ROOT_DIR, "private")
VECTORIZER_PATH = os.path.join(PRIVATE_DATA_FOLDER, "vectorizer.pkl")
MODEL_PATH = os.path.join(PRIVATE_DATA_FOLDER, "model.pkl")


# Define an Enum for expense categories
class ExpenseCategory(Enum):
    BILLS = "bills"
    ENTERTAINMENT = "entertainment"
    GROCERIES = "groceries"
    HEALTHCARE = "healthcare"
    MISCELLANEOUS = "miscellaneous"
    RENT = "rent"
    SHOPPING = "shopping"
    SOFTWARE = "software"
    TRANSPORTATION = "transportation"
    UNKNOWN = "unknown"
    UTILITIES = "utilities"


# Easiest (by expensive, time consuming), would be to use Plaid API
# Other options:
#   * Merchant Category Codes (MCCs)


# Training data will be pulled from a descriptions file
# This file will be written on each run to continue to improve the model
# Load the this from data/descriptions-data.txt
def load_descriptions():
    """
    Load descriptions and categories from a file into lists.
    Each line should be in JSON format: {"transaction": "text", "category": "category_name"}
    """
    descriptions = []
    categories = []

    try:
        with open(
            os.path.join(PRIVATE_DATA_FOLDER, "descriptions-data.json"),
            "r",
            encoding="utf-8",
        ) as f:
            data = json.load(f)  # Load the entire JSON array
            logger.info(f"Loaded {len(data)} items from JSON file")

            for item in data:
                # Make sure we're getting the right field name
                if "transaction" in item and "category" in item:
                    # Skip empty descriptions
                    if item["transaction"].strip():
                        descriptions.append(item["transaction"])
                        categories.append(item["category"])
                else:
                    logger.warning(f"Missing required fields in item: {item}")

    except FileNotFoundError:
        logger.warning(
            "descriptions-data.json not found! Make sure you run an analysis first!"
        )
        return [], []
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in descriptions-data.json: {str(e)}")
        return [], []

    logger.info(f"Loaded {len(descriptions)} valid descriptions for training")

    # Debug: Print first few descriptions
    if descriptions:
        logger.debug("First 3 descriptions:")
        for d in descriptions[:3]:
            logger.debug(f"  {d}")
    else:
        logger.warning("No valid descriptions found!")

    return descriptions, categories


def train_classifier():
    """Train classifier with case-insensitive handling"""
    training_descriptions, training_categories = load_training_data()

    if not training_descriptions:
        logger.error("No training data available!")
        return None, None

    # Create vectorizer with case-insensitive processing
    vectorizer = CountVectorizer(
        preprocessor=clean_text,  # Use our clean_text function
        stop_words=None,
        min_df=1,
        token_pattern=r"[^\s]+",
        lowercase=True,  # Make sure vectorizer handles case consistently
    )

    try:
        # Clean all training descriptions
        cleaned_descriptions = [clean_text(desc) for desc in training_descriptions]

        X = vectorizer.fit_transform(cleaned_descriptions)
        logger.info(f"Vocabulary size: {len(vectorizer.vocabulary_)}")

        model = MultinomialNB()
        model.fit(X, training_categories)

        return vectorizer, model

    except ValueError as e:
        logger.error(f"Error during training: {str(e)}")
        return None, None


def save_descriptions(descriptions_path, descriptions):
    """
    Save descriptions to a JSON file properly formatted
    """
    formatted_descriptions = []
    for desc in descriptions:
        # If it's already a dictionary, use it as is
        if isinstance(desc, dict):
            # Ensure consistent field naming
            if "description" in desc and "transaction" not in desc:
                desc["transaction"] = desc.pop("description")
            formatted_descriptions.append(desc)
        else:
            # If it's a string, create a new dictionary
            formatted_descriptions.append({"transaction": desc, "category": "unknown"})

    try:
        with open(descriptions_path, "w", encoding="utf-8") as f:
            json.dump(formatted_descriptions, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving descriptions: {str(e)}")


# For labels, use the existing ExpenseCategory for the list of them
# Generate a list of the enums above
def generate_categories():
    return [category.value for category in ExpenseCategory]


def clean_text(text):
    """Clean and standardize text for better matching"""
    # Convert to uppercase for consistency
    text = text.upper()
    # Remove special characters but keep spaces
    text = re.sub(r"[^\w\s]", " ", text)
    # Remove extra whitespace
    text = " ".join(text.split())
    return text


def load_training_data():
    """Load training data with variations"""
    training_descriptions = []
    training_categories = []

    with open(os.path.join(DATA_FOLDER, "training-categories.json"), "r") as f:
        training_data = json.load(f)

    # Add variations for each merchant
    for merchant, category in training_data.items():
        # Add original
        training_descriptions.append(merchant)
        training_categories.append(category)

        # Add with common prefixes/suffixes
        variations = [
            f"{merchant} #",
            f"{merchant} STORE",
            f"SQ *{merchant}",  # Square payments
            f"{merchant}*",
            f"{merchant} LLC",
            f"{merchant} INC",
        ]

        for variation in variations:
            training_descriptions.append(variation)
            training_categories.append(category)

    return training_descriptions, training_categories


def get_model():
    """
    Load the trained model and vectorizer from disk
    Returns:
        tuple: (vectorizer, model) or (None, None) if loading fails
    """
    try:
        with open(os.path.join(PRIVATE_DATA_FOLDER, "model.pkl"), "rb") as f:
            model = pickle.load(f)
        with open(os.path.join(PRIVATE_DATA_FOLDER, "vectorizer.pkl"), "rb") as f:
            vectorizer = pickle.load(f)
        return vectorizer, model
    except FileNotFoundError:
        logger.warning("Model files not found. Please train the model first.")
        return None, None
    except Exception as e:
        logger.error(f"Error loading model: {str(e)}")
        return None, None


def predict_category(description, vectorizer, model):
    """
    Predict category with improved case-insensitive matching
    """
    if vectorizer is None or model is None:
        return "unknown", 0.0

    # Clean and standardize the input description
    cleaned_description = clean_text(description)

    # Load training data for fuzzy matching
    training_descriptions, _ = load_training_data()

    # Try exact prediction first
    X_new = vectorizer.transform([cleaned_description])
    predicted_category = model.predict(X_new)[0]
    probabilities = model.predict_proba(X_new)[0]
    confidence = max(probabilities)

    # If confidence is low, try fuzzy matching
    if confidence < 0.3:
        best_match = None
        best_ratio = 0

        for train_desc in training_descriptions:
            # Clean both strings for comparison
            clean_train = clean_text(train_desc)

            # Try different case-insensitive fuzzy matching techniques
            ratio1 = fuzz.ratio(cleaned_description, clean_train)
            ratio2 = fuzz.partial_ratio(cleaned_description, clean_train)
            ratio3 = fuzz.token_sort_ratio(cleaned_description, clean_train)

            # Use the best matching score
            ratio = max(ratio1, ratio2, ratio3)

            if ratio > best_ratio:
                best_ratio = ratio
                best_match = train_desc

        # If we found a good fuzzy match
        if best_ratio > 70:
            X_match = vectorizer.transform([best_match])
            predicted_category = model.predict(X_match)[0]
            confidence = best_ratio / 100.0

            logger.debug(
                f"Fuzzy matched '{description}' to '{best_match}' with confidence {confidence}"
            )

    return predicted_category, confidence


def save_model(
    vectorizer, model, vectorizer_path=VECTORIZER_PATH, model_path=MODEL_PATH
):
    with open(vectorizer_path, "wb") as f:
        pickle.dump(vectorizer, f)
        print("Saved vector model to ", vectorizer_path)
    with open(model_path, "wb") as f:
        pickle.dump(model, f)
        print("Saved model to ", model_path)


def load_model(vectorizer_path=VECTORIZER_PATH, model_path=MODEL_PATH):
    with open(vectorizer_path, "rb") as f:
        vectorizer = pickle.load(f)
    with open(model_path, "rb") as f:
        model = pickle.load(f)
    return vectorizer, model


def add_training_example(description, category):
    """Add a new training example to training-categories.json"""
    try:
        with open(os.path.join(DATA_FOLDER, "training-categories.json"), "r+") as f:
            data = json.load(f)
            data[description] = category
            f.seek(0)
            json.dump(data, f, indent=4)
            f.truncate()
        logger.info(f"Added training example: {description} -> {category}")
    except Exception as e:
        logger.error(f"Error adding training example: {e}")


def categorize_transaction(description, vectorizer, model):
    category, confidence = predict_category(description, vectorizer, model)
    if confidence > 0.3:
        return category
    return "unknown"
