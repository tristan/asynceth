import asyncio
import os
from asynceth import Contract, JsonRPCClient
from asynceth.test.utils import PrivateKey, send_transaction

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
        await jsonrpc_client.close()

async def test_retry_block_number_jsonrpc(parity):
    jsonrpc_client = JsonRPCClient(parity.url())
    try:
        assert await jsonrpc_client.eth_blockNumber() == 0

        async def send_payment_soon():
            """creates a new block after 1 second"""
            await asyncio.sleep(1)
            faucet_key = PrivateKey(parity.get_faucet_private_key())
            await send_transaction(
                jsonrpc_client, faucet_key,
                "0x" + os.urandom(20).hex(),
                10 ** 18)

        task = asyncio.get_event_loop().create_task(send_payment_soon())
        await jsonrpc_client.eth_getLogs(1, 1, validate_block_number=False)
        await task

    finally:
        await jsonrpc_client.close()
