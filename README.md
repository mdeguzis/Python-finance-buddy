# Python-finance-buddy
A multi-user focused budget analysis / planning tool.

The idea for this came from the following gripes I have with modern budgeting apps:

* They are not multi-user focused
  * Transactions do not have the per-user data if your family shares the same credit card on a banking account.
    * Example: Capital One Venture X shared by multiple people. Only the PDF report contains the breakdown

* ...

## Categorization

Transaction descriptions are fed to a training model over time. 

Run the following to train the data
```
pipenv run python data/train-data.py
```

Examples:

```
$ pipenv run finance-buddy --capital-one ~/Downloads/test.pdf 
2024-12-15 04:02:46,250 - INFO - Analyzing file: /tmp/test.pdf
2024-12-15 04:02:46,250 - INFO - Detected file type: PDF
2024-12-15 04:02:46,251 - INFO - Extracting data from Capital One PDF...
2024-12-15 04:02:46,286 - INFO - Processing page 1...
2024-12-15 04:02:46,940 - INFO - Processing transactions for 'YIN RONG ALVINA TEO' (Account #YIN RONG ALVINA TEO #5611: Transactions)
2024-12-15 04:02:46,942 - INFO - Predicted food for description 'TST*FOODPLACE"
```

When you see low confidence matches, update known categories in
* `data/training-categories.json`
* `finance_buddy/classification.py` > `ExpenseCategory`
* Avoid adding tranining data that would be considered personal

```
pipenv run python data/train-data.py

================================================================================
Making predictions on sample data...
================================================================================
Attempting to predict category for: CHIPOTLE USAPAVAFL
Predicted category: food (confidence: 0.62)

================================================================================
Making predictions on full data...
================================================================================
Attempting to predict category for: GRAMMARLY CO
Predicted category: software (confidence: 0.37)

================================================================================
Low confidence / unknowns:
================================================================================
['SPOTHERO 231234232134', '0.38']
['SOME RANDOM BAKERY AND', '0.38']
```

This dataset is what is used to guess the categories for the transactions when the program is ran. 
In the future, other resources may be leveraged:

* Flexible Search Function
* Merchant Category Codes (MCCs)
* Fuzzy Matching
