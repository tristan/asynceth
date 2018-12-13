import os
import asyncio
import rlp
from ethereum.utils import privtoaddr, encode_hex, sha3 as keccak256, ecsign, zpad, bytearray_to_bytestr, int_to_32bytearray
from eth_utils import decode_hex
from asynceth.contract.transaction import Transaction

class PrivateKey:
    def __init__(self, key=None):
        if key is None:
            key = os.urandom(32)
        elif isinstance(key, str):
            key = decode_hex(key)
        self.key = key

    @property
    def address(self):
        return '0x' + encode_hex(privtoaddr(self.key))

    def sign(self, payload):
        rawhash = keccak256(payload)

        v, r, s = ecsign(rawhash, self.key)
        signature = \
            zpad(bytearray_to_bytestr(int_to_32bytearray(r)), 32) + \
            zpad(bytearray_to_bytestr(int_to_32bytearray(s)), 32) + \
            bytearray_to_bytestr([v])

        return signature

async def send_transaction(jsonrpc, key, to, value, startgas=None, gasprice=None, nonce=None, data=b"", network_id=None):

    to = decode_hex(to)
    if len(to) not in (20, 0):
        raise Exception('Addresses must be 20 or 0 bytes long (len was {})'.format(len(to)))

    bulk = jsonrpc.bulk()
    if nonce is None:
        nonce = bulk.eth_getTransactionCount(key.address)
    else:
        nonce_future = asyncio.get_event_loop().create_future()
        nonce_future.set_result(nonce)
        nonce = nonce_future

    balance = bulk.eth_getBalance(key.address)

    if gasprice is None:
        gasprice = bulk.eth_gasPrice()
    else:
        gasprice_future = asyncio.get_event_loop().create_future()
        gasprice_future.set_result(gasprice)
        gasprice = gasprice_future

    if startgas is None:
        startgas = bulk.eth_estimateGas(
            key.address, to, data=data, value=value)
    else:
        startgas_future = asyncio.get_event_loop().create_future()
        startgas_future.set_result(startgas)
        startgas = startgas_future

    if network_id is None:
        network_id = bulk.net_version()
    else:
        if isinstance(network_id, int):
            network_id = str(network_id)
        network_id_future = asyncio.get_event_loop().create_future()
        network_id_future.set_result(network_id)
        network_id = network_id_future

    await bulk.execute()
    nonce = await nonce
    balance = await balance
    gasprice = await gasprice
    startgas = await startgas
    network_id = int(await network_id)

    tx = Transaction(nonce, gasprice, startgas, to, value, data, network_id, 0, 0)

    if balance < (tx.value + (tx.startgas * tx.gasprice)):
        raise Exception("Address doesn't have enough funds")

    tx = tx.sign(key.key, network_id=network_id)

    tx_encoded = '0x' + encode_hex(rlp.encode(tx, Transaction))

    tx_hash = await jsonrpc.eth_sendRawTransaction(tx_encoded)

    return tx_hash

def make_word(description: str) -> bytes:
    r"""
    Converts a "description" of a 32-byte word into a 32-byte word.  A
    description is either a hex representation of a byte string (e.g.
    'deafbeef') or a hex representation along with a fill directive
    'leftpadchar<' or '>rightpadchar'.

    Examples:
    >>> # Left padding examples
    >>> assert make_word('0<deadbeef') == zpad32(b'\xde\xad\xbe\xef')
    >>> assert make_word('f<deadbeef') == fpad32(b'\xde\xad\xbe\xef')
    >>> assert make_word('deadbeef') == zpad32(b'\xde\xad\xbe\xef')
    >>> # Right padding examples
    >>> assert make_word('deadbeef>0') == zpad32_right(b'\xde\xad\xbe\xef')
    """
    if '<' in description:
        fill_char, hex_str = description.split('<')
        return decode_hex(hex_str.rjust(64, fill_char))

    if '>' in description:
        hex_str, fill_char = description.split('>')
        return decode_hex(hex_str.ljust(64, fill_char))

    return decode_hex(description.rjust(64, '0'))


def words(*descriptions: str) -> bytes:
    r"""
    Converts multiple word descriptions into 32-byte words joined into a single
    byte string.

    Examples:
    >>> assert words('1') == zpad32(b'\x01')
    >>> assert words('1', '2f>0') == zpad32(b'\x01') + zpad32_right(b'\x2f')
    """
    return b''.join(make_word(d) for d in descriptions)

def print_words(data):
    if isinstance(data, str):
        data = decode_hex(data)
    for i in range(0, len(data), 32):
        print(data[i:i + 32].hex())
