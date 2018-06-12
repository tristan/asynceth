import asyncio
import ethereum.abi
import rlp

from ethereum.transactions import Transaction
from ethereum.utils import encode_hex, decode_hex, privtoaddr

from asynceth.contract.utils import compile_solidity

class ContractTranslator(ethereum.abi.ContractTranslator):
    def __init__(self, contract_interface):
        super().__init__(contract_interface)

class ContractMethod:

    def __init__(self, name, contract):
        self.name = name
        self.contract = contract
        # TODO: forcing const seems to do nothing, since eth_call
        # will just return a tx_hash (on parity at least)
        self.is_constant = self.contract.translator.function_data[name]['is_constant']

    @property
    def jsonrpc(self):
        return self.contract.jsonrpc

    async def __call__(self, *args, startgas=None, gasprice=None, value=0, nonce=None):
        # TODO: figure out if we can validate args
        validated_args = []
        for (type, name), arg in zip(self.contract.translator.function_data[self.name]['signature'], args):
            if type == 'address' and isinstance(arg, str):
                validated_args.append(decode_hex(arg))
            elif (type.startswith("uint") or type.startswith("int")) and isinstance(arg, str):
                validated_args.append(int(arg, 16))
            else:
                validated_args.append(arg)

        data = self.contract.translator.encode_function_call(self.name, validated_args)

        if self.is_constant:
            result = await self.jsonrpc.eth_call(
                from_address=self.contract.signer_address or '',
                to_address=self.contract.address,
                data=data)
            result = decode_hex(result)
            if result:
                decoded = self.contract.translator.decode_function_result(self.name, result)
                # decode string results
                decoded = [val.decode('utf-8') if isinstance(val, bytes) and type == 'string' else val
                           for val, type in zip(decoded, self.contract.translator.function_data[self.name]['decode_types'])]
                # return the single value if there is only a single return value
                if len(decoded) == 1:
                    return decoded[0]
                return decoded
            return None

        if self.contract.private_key is None or self.contract.signer_address is None:
            raise Exception("Cannot call non-constant function without a signer")

        if nonce is None:
            nonce = await self.jsonrpc.eth_getTransactionCount(self.contract.signer_address)
        balance = await self.jsonrpc.eth_getBalance(self.contract.signer_address)

        if gasprice is None:
            gasprice = await self.jsonrpc.eth_gasPrice()

        if startgas is None:
            startgas = await self.jsonrpc.eth_estimateGas(
                self.contract.signer_address, self.contract.address, data=data,
                nonce=nonce, value=value, gasprice=gasprice)
            if startgas == 50000000 or startgas is None:
                raise Exception("Unable to estimate startgas")

        if balance < (startgas * gasprice):
            raise Exception("Given account doesn't have enough funds")

        tx = Transaction(nonce, gasprice, startgas, self.contract.address, value, data, 0, 0, 0)
        tx = tx.sign(self.contract.private_key)
        tx_encoded = '0x' + encode_hex(rlp.encode(tx, Transaction))

        tx_hash = await self.jsonrpc.eth_sendRawTransaction(tx_encoded)
        while True:
            receipt = await self.jsonrpc.eth_getTransactionReceipt(tx_hash)
            if receipt is None or receipt['blockNumber'] is None:
                await asyncio.sleep(0.1)
            else:
                if 'status' in receipt and receipt['status'] != "0x1":
                    raise Exception("Transaction status returned {}".format(receipt['status']))
                return receipt

class Contract:

    def __init__(self, jsonrpc, abi, bytecode=None, address=None):
        if isinstance(abi, str):
            abi, bytecode = compile_solidity(abi)
        self.abi = abi
        self.bytecode = bytecode
        self.jsonrpc = jsonrpc
        self.valid_funcs = [part['name'] for part in abi if part['type'] == 'function']
        self.translator = ContractTranslator(abi)
        self.address = address
        self.private_key = None
        self.signer_address = None

    def set_signer(self, private_key):
        if isinstance(private_key, str):
            private_key = decode_hex(private_key)
        if not isinstance(private_key, bytes) or len(private_key) != 32:
            raise Exception("Invalid private key")
        self.private_key = private_key
        self.signer_address = '0x' + encode_hex(privtoaddr(private_key))
        return self

    async def deploy(self, *constructor_data, private_key=None, gasprice=None, startgas=None, nonce=None, value=0):
        if private_key is None and self.private_key is None:
            raise Exception("Missing private key")
        elif private_key is None:
            private_key = self.private_key
        else:
            if isinstance(private_key, str):
                private_key = decode_hex(private_key)
            if not isinstance(private_key, bytes) or len(private_key) != 32:
                raise Exception("Invalid private key")

        bytecode = self.bytecode
        if constructor_data:
            constructor_call = self.translator.encode_constructor_arguments(constructor_data)
            bytecode += constructor_call

        if nonce is None:
            nonce = await self.jsonrpc.eth_getTransactionCount(self.signer_address)
        balance = await self.jsonrpc.eth_getBalance(self.signer_address)

        if gasprice is None:
            gasprice = await self.jsonrpc.eth_gasPrice()

        if startgas is None:
            startgas = await self.jsonrpc.eth_estimateGas(
                self.signer_address, '', data=bytecode,
                nonce=nonce, value=value, gasprice=gasprice)
            if startgas == 50000000 or startgas is None:
                raise Exception("Unable to estimate startgas")

        if balance < (startgas * gasprice):
            raise Exception("Given account doesn't have enough funds")

        tx = Transaction(nonce, gasprice, startgas, b'', value, bytecode, 0, 0, 0)
        tx = tx.sign(private_key)

        tx_encoded = '0x' + encode_hex(rlp.encode(tx, Transaction))

        self.address = '0x' + encode_hex(tx.creates)

        tx_hash = await self.jsonrpc.eth_sendRawTransaction(tx_encoded)

        while True:
            resp = await self.jsonrpc.eth_getTransactionByHash(tx_hash)
            if resp is None or resp['blockNumber'] is None:
                await asyncio.sleep(0.1)
            else:
                code = await self.jsonrpc.eth_getCode(self.address)
                if code == '0x':
                    raise Exception("Failed to deploy contract: resulting address '{}' has no code".format(self.address))
                return self

    def __getattribute__(self, name):
        address = super().__getattribute__('address')
        valid_funcs = super().__getattribute__('valid_funcs')
        if address is not None and name in valid_funcs:
            return ContractMethod(name, self)
        return super().__getattribute__(name)
