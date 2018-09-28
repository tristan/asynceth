import asyncio
import ethereum.abi
import rlp
import json

from ethereum.utils import encode_hex, decode_hex, privtoaddr, zpad, encode_int
from eth_abi import encode_abi, decode_abi
from asynceth.contract.utils import compile_solidity
from ethereum.abi import normalize_name, method_id, event_id

from asynceth.contract.transaction import TransactionResponse, Transaction

def process_abi_type(type_abi):
    """Converts `tuple` (i.e struct) types into the (type1,type2,type3) form"""
    typ = type_abi['type']
    if typ.startswith('tuple'):
        type_str = '(' + ','.join(process_abi_type(component) for component in type_abi['components']) + ')'
        if typ[-1] == ']':
            type_str += typ[5:]
        return type_str
    return type_abi['type']

class ContractTranslator(ethereum.abi.ContractTranslator):
    def __init__(self, contract_interface):
        if isinstance(contract_interface, str):
            contract_interface = json.dumps(contract_interface)

        self.fallback_data = None
        self.constructor_data = None
        self.function_data = {}
        self.event_data = {}

        for description in contract_interface:
            entry_type = description.get('type', 'function')
            encode_types = []
            signature = []

            # If it's a function/constructor/event
            if entry_type != 'fallback' and 'inputs' in description:
                encode_types = []
                signature = []
                for element in description.get('inputs', []):
                    encode_type = process_abi_type(element)
                    encode_types.append(encode_type)
                    signature.append((encode_type, element['name']))

            if entry_type == 'function':
                normalized_name = normalize_name(description['name'])
                prefix = method_id(normalized_name, encode_types)

                decode_types = []
                for element in description.get('outputs', []):
                    decode_type = process_abi_type(element)
                    decode_types.append(decode_type)

                self.function_data[normalized_name] = {
                    'prefix': prefix,
                    'encode_types': encode_types,
                    'decode_types': decode_types,
                    'is_constant': description.get('constant', False),
                    'signature': signature,
                    'payable': description.get('payable', False),
                }

            elif entry_type == 'event':
                normalized_name = normalize_name(description['name'])

                indexed = [
                    element['indexed']
                    for element in description['inputs']
                ]
                names = [
                    element['name']
                    for element in description['inputs']
                ]
                # event_id == topics[0]
                self.event_data[event_id(normalized_name, encode_types)] = {
                    'types': encode_types,
                    'name': normalized_name,
                    'names': names,
                    'indexed': indexed,
                    'anonymous': description.get('anonymous', False),
                }

            elif entry_type == 'constructor':
                if self.constructor_data is not None:
                    raise ValueError('Only one constructor is supported.')

                self.constructor_data = {
                    'encode_types': encode_types,
                    'signature': signature,
                }

            elif entry_type == 'fallback':
                if self.fallback_data is not None:
                    raise ValueError(
                        'Only one fallback function is supported.')
                self.fallback_data = {'payable': description['payable']}

            else:
                raise ValueError('Unknown type {}'.format(description['type']))

    def encode_function_call(self, function_name, args):
        if function_name not in self.function_data:
            raise ValueError('Unkown function {}'.format(function_name))
        description = self.function_data[function_name]
        function_selector = zpad(encode_int(description['prefix']), 4)
        arguments = encode_abi(description['encode_types'], args)
        return function_selector + arguments

    def decode_function_result(self, function_name, data):
        description = self.function_data[function_name]
        arguments = decode_abi(description['decode_types'], data)
        return arguments

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

    async def estimate_gas(self, *args, value=0, nonce=None, gasprice=None):
        if self.is_constant:
            return 0
        validated_args = self.validate_arguments(*args)
        data = self.contract.translator.encode_function_call(self.name, validated_args)
        kwargs = {}
        if nonce is not None:
            kwargs['nonce'] = nonce
        if gasprice is not None:
            kwargs['gasprice'] = gasprice

        return await self.jsonrpc.eth_estimateGas(
            self.contract.signer_address, self.contract.address, data=data, value=value, **kwargs)

    def data(self, *args):
        validated_args = self.validate_arguments(*args)
        return self.contract.translator.encode_function_call(self.name, validated_args)

    def validate_arguments(self, *args):
        validated_args = []
        for (type, name), arg in zip(self.contract.translator.function_data[self.name]['signature'], args):
            if type == 'address' and isinstance(arg, str):
                validated_args.append(decode_hex(arg))
            elif (type.startswith("uint") or type.startswith("int")) and isinstance(arg, str):
                validated_args.append(int(arg, 16))
            else:
                validated_args.append(arg)
        return validated_args

    def __call__(self, *args, startgas=None, gasprice=None, value=0, nonce=None, network_id=None, bulk=None):
        validated_args = self.validate_arguments(*args)

        data = self.contract.translator.encode_function_call(self.name, validated_args)

        if self.is_constant:

            def result_processor(result):
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

            if bulk is not None:
                return bulk.eth_call(
                    from_address=self.contract.signer_address or '',
                    to_address=self.contract.address,
                    data=data, result_processor=result_processor)
            # async
            return self.jsonrpc.eth_call(
                from_address=self.contract.signer_address or '',
                to_address=self.contract.address,
                data=data, result_processor=result_processor)

        if bulk is not None:
            raise Exception("Cannot call non-constant function within a bulk call")

        if self.contract.private_key is None or self.contract.signer_address is None:
            raise Exception("Cannot call non-constant function without a signer")

        # async
        return self._async__call__(data=data, startgas=startgas, gasprice=gasprice, value=value, nonce=nonce, network_id=network_id)

    async def _async__call__(self, *, data, startgas=None, gasprice=None, value=0, nonce=None, network_id=None):

        bulk = self.jsonrpc.bulk()
        if nonce is None:
            nonce = bulk.eth_getTransactionCount(self.contract.signer_address)
        else:
            nonce_future = asyncio.get_event_loop().create_future()
            nonce_future.set_result(nonce)
            nonce = nonce_future

        balance = bulk.eth_getBalance(self.contract.signer_address)

        if gasprice is None:
            gasprice = bulk.eth_gasPrice()
        else:
            gasprice_future = asyncio.get_event_loop().create_future()
            gasprice_future.set_result(gasprice)
            gasprice = gasprice_future

        if startgas is None:
            startgas = bulk.eth_estimateGas(
                self.contract.signer_address, self.contract.address,
                data=data, value=value)
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

        if startgas == 50000000 or startgas is None:
            raise Exception("Unable to estimate startgas")

        if balance < (startgas * gasprice):
            raise Exception("Given account doesn't have enough funds")

        tx = Transaction(nonce, gasprice, startgas, self.contract.address, value, data, 0, 0, 0)
        tx = tx.sign(self.contract.private_key, network_id=network_id)
        tx_encoded = '0x' + encode_hex(rlp.encode(tx, Transaction))

        tx_hash = await self.jsonrpc.eth_sendRawTransaction(tx_encoded)
        return TransactionResponse(self.jsonrpc, tx_hash)

class Contract:

    def __init__(self, jsonrpc, abi, name=None, cwd=None, bytecode=None, address=None, optimize=True, optimize_runs=1000000000):
        if isinstance(abi, str):
            abi, bytecode = compile_solidity(abi, cwd=cwd, name=name, optimize=optimize, optimize_runs=optimize_runs)
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

    async def deploy(self, *constructor_data, private_key=None, gasprice=None, startgas=None, nonce=None, value=0, network_id=None):
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

        bulk = self.jsonrpc.bulk()
        if nonce is None:
            nonce = bulk.eth_getTransactionCount(self.signer_address)
        else:
            nonce_future = asyncio.get_event_loop().create_future()
            nonce_future.set_result(nonce)
            nonce = nonce_future

        balance = bulk.eth_getBalance(self.signer_address)

        if gasprice is None:
            gasprice = bulk.eth_gasPrice()
        else:
            gasprice_future = asyncio.get_event_loop().create_future()
            gasprice_future.set_result(gasprice)
            gasprice = gasprice_future

        if startgas is None:
            startgas = bulk.eth_estimateGas(
                self.signer_address, '',
                data=bytecode, value=value)
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
