import asyncio

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
