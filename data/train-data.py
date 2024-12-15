#!/usr/bin/env python

from finance_buddy import classification

# Train the model
print("Training the model...")
vectorizer, model = classification.train_classifier()

# Save the model
print("Saving the model...")
classification.save_model(vectorizer, model)

# Make predictions
print("Making predictions...")

descriptions = [
    "CHIPOTLE 0203HERNDONVA",
    "PRT CRYSTAL PLACE703-9205600VA",
    "SQ *CAFE AMAZONSomethingUSA",
]
for description in descriptions:
    print("\nAttempting to predict category for: " + description)
    category, confidence = classification.predict_category(description, vectorizer, model)
    print(f"Predicted category: {category} (confidence: {confidence:.2f})")

# To use the model later
#vectorizer, model = classification.load_model()
