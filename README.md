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

This dataset is what is used to guess the categories for the transactions when the program is ran. 
In the future, other resources may be leveraged:

* Flexible Search Function
* Merchant Category Codes (MCCs)
* Fuzzy Matching
