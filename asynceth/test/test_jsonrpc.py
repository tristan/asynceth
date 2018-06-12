
from asynceth import Contract, JsonRPCClient
from asynceth.test.utils import PrivateKey

async def test_jsonrpc(parity):
    jsonrpc_client = JsonRPCClient(parity.url())
    try:
        assert await jsonrpc_client.eth_blockNumber() == 0

        faucet_key = PrivateKey(parity.get_faucet_private_key())

        assert await jsonrpc_client.eth_getBalance(faucet_key.address) != 0

        token = await Contract(
            jsonrpc_client, "asynceth/test/ERC20Token.sol")\
            .set_signer(faucet_key.key)\
            .deploy(2**256 - 1, "Token", 18, "TOK")

        assert await token.name() == "Token"
        assert await token.balanceOf(faucet_key.address) == 2**256 - 1
        test_key = PrivateKey()
        await token.transfer(test_key.address, 10 ** 18)
        assert await token.balanceOf(test_key.address) == 10 ** 18
    finally:
        await jsonrpc_client.clse()
