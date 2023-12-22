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

def escape_xlsx_char(ch):
	illegal_xlsx_chars = {
	'\x00':'\\x00',	#	NULL
	'\x01':'\\x01',	#	SOH
	'\x02':'\\x02',	#	STX
	'\x03':'\\x03',	#	ETX
	'\x04':'\\x04',	#	EOT
	'\x05':'\\x05',	#	ENQ
	'\x06':'\\x06',	#	ACK
	'\x07':'\\x07',	#	BELL
	'\x08':'\\x08',	#	BS
	'\x0b':'\\x0b',	#	VT
	'\x0c':'\\x0c',	#	FF
	'\x0e':'\\x0e',	#	SO
	'\x0f':'\\x0f',	#	SI
	'\x10':'\\x10',	#	DLE
	'\x11':'\\x11',	#	DC1
	'\x12':'\\x12',	#	DC2
	'\x13':'\\x13',	#	DC3
	'\x14':'\\x14',	#	DC4
	'\x15':'\\x15',	#	NAK
	'\x16':'\\x16',	#	SYN
	'\x17':'\\x17',	#	ETB
	'\x18':'\\x18',	#	CAN
	'\x19':'\\x19',	#	EM
	'\x1a':'\\x1a',	#	SUB
	'\x1b':'\\x1b',	#	ESC
	'\x1c':'\\x1c',	#	FS
	'\x1d':'\\x1d',	#	GS
	'\x1e':'\\x1e',	#	RS
	'\x1f':'\\x1f'}	#	US
	
	if ch in illegal_xlsx_chars:
		return illegal_xlsx_chars[ch]
	
	return ch
	
#
# Wraps the function escape_xlsx_char(ch).
def escape_xlsx_string(st):
	
	return ''.join([escape_xlsx_char(ch) for ch in st])