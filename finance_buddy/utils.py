from decimal import Decimal


# Default json library doesn't like to serialize decimal :)
# Convert Decimal objects to strings before serializing to JSON
def decimal_default(obj):
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError("Object of type Decimal is not JSON serializable")
