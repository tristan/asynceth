import regex
import binascii

from decimal import Decimal

str_types = str

HEX_STRING_RE = regex.compile('^(?:0[xX])([0-9a-fA-F]+)$')
INT_STRING_RE = regex.compile('^(-?(?:0|[1-9][0-9]*))$')
DECIMAL_STRING_RE = regex.compile('^(-?(0|[1-9][0-9]*)\.[0-9]+)$')
ETH_ADDRESS_RE = regex.compile('^(?:0[xX])([0-9a-fA-F]{40})$')

def validate_address(addr):
    return isinstance(addr, str_types) and ETH_ADDRESS_RE.match(addr) is not None

def validate_signature(sig):
    return isinstance(sig, str_types) and HEX_STRING_RE.match(sig) is not None and len(sig) == 132

def validate_transaction_hash(sig):
    return isinstance(sig, str_types) and HEX_STRING_RE.match(sig) is not None and len(sig) == 66

def validate_hex_string(value):
    # NOTE: it is a requirement that hex strings begin with 0x to
    # remove any ambiguity over the type of numbers encoded as strings
    return isinstance(value, str_types) and HEX_STRING_RE.match(value) is not None

def validate_int_string(value):
    return isinstance(value, str_types) and INT_STRING_RE.match(value) is not None

def validate_decimal_string(value):
    return isinstance(value, str_types) and DECIMAL_STRING_RE.match(value) is not None

def parse_int(value):
    """Safer version of python's `int` that does intermediate conversions
    of other number types when represented as a string before passing them
    to int rather than simply failing, returns None if the type is not
    supported"""

    if isinstance(value, int):
        return value
    if isinstance(value, (float, Decimal)):
        return int(value)
    if isinstance(value, bytes):
        value = value.decode('ascii', 'replace')
    if isinstance(value, str_types):
        if len(value) and value[0] == '-':
            multiplier = -1
            value = value[1:]
        else:
            multiplier = 1
        if validate_hex_string(value):
            return int(value[2:], 16) * multiplier
        if validate_int_string(value):
            return int(value) * multiplier
        if validate_decimal_string(value):
            return int(float(value)) * multiplier
    return None

def parse_boolean(b):
    if isinstance(b, bool):
        return b
    elif isinstance(b, str):
        b = b.lower()
        if b == 'true':
            return True
        elif b == 'false':
            return False
        else:
            return None
    elif isinstance(b, int):
        return bool(b)
    return None

def validate_hex_int(value, length=None):
    if isinstance(value, int):
        if value < 0:
            raise ValueError("Negative values are unsupported")
        value = hex(value)[2:]
    elif isinstance(value, bytes):
        value = binascii.b2a_hex(value).decode('ascii')
    else:
        m = HEX_STRING_RE.match(value)
        if m:
            value = m.group(1)
        else:
            raise ValueError("Unable to convert value to valid hex string")
    if length:
        if len(value) > length * 2:
            raise ValueError("Value is too long")
        return '0x' + value.rjust(length * 2, '0')
    return '0x' + value

def validate_block_param(param):

    if param not in ("earliest", "latest", "pending"):
        return validate_hex_int(param)
    return param
