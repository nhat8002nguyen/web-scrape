def format_currency(value):
    value_str = str(value)
    # If the value is less than 100, we assume it represents only cents
    if value < 100:
        return value_str.zfill(2).lstrip('0') + " cents"  # Stripping leading zeros
    else:
        # Insert a decimal point before the last two digits
        integer_part = value_str[:-2]
        decimal_part = value_str[-2:].lstrip('0')  # Stripping trailing zeros
        # Format the integer part with commas
        formatted_integer = "{:,}".format(int(integer_part))
        if decimal_part:  # Check if there's anything left in decimal_part after stripping
            return f"{formatted_integer}.{decimal_part}"
        else:
            return formatted_integer