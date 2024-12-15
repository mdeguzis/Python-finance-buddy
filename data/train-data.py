#!/usr/bin/env python

import logging
from finance_buddy import classification

logger = logging.getLogger(__name__)

LOW_CONDFIDENCE = 0.50


def train_and_save():
    """Train and save the model"""
    print("Training the model...")
    vectorizer, model = classification.train_classifier()

    if vectorizer and model:
        print("Saving the model...")
        classification.save_model(vectorizer, model)
    else:
        logger.error("Failed to train model")
        return


def test_predictions():
    """Load model and test predictions"""
    # Load the saved model
    vectorizer, model = classification.get_model()

    if not vectorizer or not model:
        logger.error("Could not load model. Please train first.")
        return

    # Test descriptions
    unknowns = []
    descriptions = [
        "CHIPOTLE USAPAVAFL",
        "PRT CRYSTAL PLACE703-9205600VA",
        "SQ *CAFE AMAZONSomethingUSA",
        "GOOGLE *CBS Mobile",
    ]

    print("=" * 80)
    print("Making predictions on sample data...")
    print("=" * 80)
    for description in descriptions:
        print(f"\nAttempting to predict category for: {description}")
        category, confidence = classification.predict_category(
            description, vectorizer, model
        )
        print(f"Predicted category: {category} (confidence: {confidence:.2f})")
        if category == "unknown" or confidence < LOW_CONDFIDENCE:
            unknowns.append([description, f"{category}", f"{confidence:.2f}"])
    print()

    print("=" * 80)
    print("Making predictions on full data...")
    print("=" * 80)
    all_descriptions, categories = classification.load_descriptions()
    for description in all_descriptions:
        print(f"\nAttempting to predict category for: {description}")
        category, confidence = classification.predict_category(
            description, vectorizer, model
        )
        print(f"Predicted category: {category} (confidence: {confidence:.2f})")
        if category == "unknown" or confidence < LOW_CONDFIDENCE:
            unknowns.append([description, f"{category}", f"{confidence:.2f}"])
    print()

    # Report unknowns to fix
    if unknowns:
        print("=" * 80)
        print("Low confidence / unknowns:")
        print("=" * 80)
        for unknown in unknowns:
            print(unknown)
    print()


def main():
    # Only train and save if you have new training data
    # Maybe make this and arg
    train_and_save()

    # Make predictions using saved model
    test_predictions()


if __name__ == "__main__":
    main()
