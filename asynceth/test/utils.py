import os
from ethereum.utils import privtoaddr, decode_hex, encode_hex, sha3 as keccak256, ecsign, zpad, bytearray_to_bytestr, int_to_32bytearray

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
