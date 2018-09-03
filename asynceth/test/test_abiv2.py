from ethereum.utils import sha3 as keccak256, decode_hex
from asynceth.test.utils import words

async def test_f(jsonrpc, abiv2_contract):
    method_id = keccak256("f((uint256,uint256[],(uint256,uint256)[]),(uint256,uint256),uint256)")[:4].hex()
    data = words('80', '8', '9', 'a', '1', '60', 'c0', '2', '2', '3', '2', '4', '5', '6', '7').hex()
    data = "0x{method_id}{data}".format(method_id=method_id, data=data)
    await jsonrpc.eth_call(to_address=abiv2_contract.address,
                           data=data)

    function_input = ((1, (2, 3), ((4, 5), (6, 7))), (8, 9), 10)
    await abiv2_contract.f(*function_input)

async def test_g(jsonrpc, abiv2_contract):
    rval = await abiv2_contract.g()
    assert rval == [(1, (2, 3), ((4, 5), (6, 7))), (8, 9), 10]

async def test_array_output(jsonrpc, abiv2_contract):

    method_id = keccak256("testArrayOutput()")[:4].hex()
    rval = await jsonrpc.eth_call(to_address=abiv2_contract.address,
                                  data="0x" + method_id)
    assert decode_hex(rval) == words('20', '2', '1', '2')
    assert await abiv2_contract.testArrayOutput() == (1, 2)

async def test_multidimensional_array_output(jsonrpc, abiv2_contract):

    method_id = keccak256("testMultidimensionalArrayOutput()")[:4].hex()
    rval = await jsonrpc.eth_call(to_address=abiv2_contract.address,
                                  data="0x" + method_id)
    assert decode_hex(rval) == words('20', '2', '40', 'a0', '2', '1', '2', '2', '3', '4')
    assert await abiv2_contract.testMultidimensionalArrayOutput() == ((1, 2), (3, 4))

async def test_struct_with_multidimensional_array_output(jsonrpc, abiv2_contract):
    method_id = keccak256("testStructWithMultidimensionalArrayOutput()")[:4].hex()
    rval = await jsonrpc.eth_call(to_address=abiv2_contract.address,
                                  data="0x" + method_id)
    assert decode_hex(rval) == words('20', '20', '2', '40', 'a0', '2', '1', '2', '2', '3', '4')
    rval = await abiv2_contract.testStructWithMultidimensionalArrayOutput()
    assert rval == (((1, 2), (3, 4)),)

async def test_struct_with_multidimensional_array_input(jsonrpc, abiv2_contract):
    method_id = keccak256("testStructWithMultidimensionalArrayInput((uint256[][]))")[:4].hex()
    data = words('20', '20', '2', '40', 'a0', '2', '1', '2', '2', '3', '4').hex()
    rval = await jsonrpc.eth_call(to_address=abiv2_contract.address,
                                  data="0x" + method_id + data)
    assert int(rval, 16) == 10
    assert await abiv2_contract.testStructWithMultidimensionalArrayInput((((1, 2), (3, 4)),)) == 10

async def test_struct_array_input(jsonrpc, abiv2_contract):
    method_id = keccak256("testStructArrayInput((uint256,uint256)[])")[:4].hex()
    struct_array = [(1, 2), (3, 4)]
    data = "0x{method_id}{data_offset:064x}{num_elements:064x}{elements}".format(
        method_id=method_id, data_offset=32, num_elements=len(struct_array),
        elements="".join(["{0:064x}{1:064x}".format(*struct) for struct in struct_array]))
    rval = await jsonrpc.eth_call(to_address=abiv2_contract.address,
                                  data=data)
    assert int(rval[2:], 16) == 10
    assert await abiv2_contract.testStructArrayInput(struct_array) == 10

async def test_struct_multidimensional_array_output(jsonrpc, abiv2_contract):
    method_id = keccak256("testStructMultidimensionalArrayOutput()")[:4].hex()
    rval = await jsonrpc.eth_call(to_address=abiv2_contract.address,
                                  data="0x" + method_id)
    assert decode_hex(rval) == words('20', '40', 'e0', '2', '1', '2', '3', '4', '2', '5', '6', '7', '8')
    rval = await abiv2_contract.testStructMultidimensionalArrayOutput()
    assert rval == (((1, 2), (3, 4)), ((5, 6), (7, 8)))

async def test_multidimensional_array_input(jsonrpc, abiv2_contract):

    method_id = keccak256("testMultidimensionalArrayInput(uint256[][])")[:4].hex()
    data = "0x" + method_id + words('20', '2', '40', 'a0', '2', '1', '2', '2', '3', '4').hex()
    rval = await jsonrpc.eth_call(to_address=abiv2_contract.address,
                                  data=data)
    assert int(rval, 16) == 10

    assert await abiv2_contract.testMultidimensionalArrayInput(((1, 2), (3, 4))) == 10
