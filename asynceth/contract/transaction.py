import asyncio

import rlp
import ethereum.transactions
from ethereum import utils
from ethereum.utils import normalize_key, ecsign
from ethereum.transactions import unsigned_tx_from_tx, UnsignedTransaction

# NOTE: this is to hotfix a bug in pyethereum's signing functions
# fixed in https://github.com/ethereum/pyethereum/commit/d962694be03686a8e5c1d7459ae272b70a5c9f77
# but not yet included in a release
class Transaction(ethereum.transactions.Transaction):
    def sign(self, key, network_id=None):
        """Sign this transaction with a private key.

        A potentially already existing signature would be overridden.
        """
        if network_id is None:
            rawhash = utils.sha3(rlp.encode(unsigned_tx_from_tx(self), UnsignedTransaction))
        else:
            assert 1 <= network_id < 2**63 - 18
            rlpdata = rlp.encode(rlp.infer_sedes(self).serialize(self)[
                                 :-3] + [network_id, b'', b''])
            rawhash = utils.sha3(rlpdata)

        key = normalize_key(key)

        v, r, s = ecsign(rawhash, key)
        if network_id is not None:
            v += 8 + network_id * 2

        ret = self.copy(
            v=v, r=r, s=s
        )
        ret._sender = utils.privtoaddr(key)
        return ret

class TransactionResponse:
    def __init__(self, jsonrpc, hash):
        self.jsonrpc = jsonrpc
        self.hash = hash
        self._receipt = None

    async def status(self):
        receipt = await self.receipt()
        if receipt is None or receipt['blockNumber'] is None:
            return 'unconfirmed'
        return 'confirmed'

    async def receipt(self):
        if self._receipt:
            return self._receipt
        receipt = await self.jsonrpc.eth_getTransactionReceipt(self.hash)
        # cache result if the transaction is included in a block
        if receipt is not None and receipt['blockNumber'] is not None:
            self._receipt = receipt
        return receipt

    async def wait_for_confirmation(self):
        while (await self.status()) != 'confirmed':
            await asyncio.sleep(1)
        return await self.receipt()

    def __await__(self):
        return self.wait_for_confirmation().__await__()
