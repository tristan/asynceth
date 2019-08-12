from asynceth import JsonRPCClient
from asynceth.test.utils import PrivateKey, send_transaction

class RequestCounter:
    def __init__(self):
        self.reqs = {}

    def count(self, data):
        if type(data) == list:
            for req in data:
                self.count(req)
            return

        method = data['method']
        if method not in self.reqs:
            self.reqs[method] = 1
        else:
            self.reqs[method] += 1

async def test_middleware(parity):
    jsonrpc_client = JsonRPCClient(parity.url())
    counter = RequestCounter()
    jsonrpc_client.middleware.before_request.append(counter.count)

    faucet_key = PrivateKey(parity.get_faucet_private_key())
    test_key = PrivateKey()

    await jsonrpc_client.eth_getBalance(faucet_key.address)
    await jsonrpc_client.eth_getBalance(test_key.address)

    await send_transaction(
        jsonrpc_client, faucet_key,
        test_key.address,
        10 ** 18)

    await jsonrpc_client.eth_getBalance(faucet_key.address)
    await jsonrpc_client.eth_getBalance(test_key.address)

    await jsonrpc_client.close()

    print(counter.reqs)

    assert counter.reqs['eth_getBalance'] == 5
    assert counter.reqs['eth_sendRawTransaction'] == 1
    assert counter.reqs['eth_getTransactionCount'] == 1
    assert counter.reqs['eth_gasPrice'] == 1
    assert counter.reqs['eth_estimateGas'] == 1
    assert counter.reqs['net_version'] == 1
