import asyncio
import random
import logging
import time

from asynceth.jsonrpc.errors import JsonRPCError, HTTPError
from asynceth.utils import parse_int, validate_hex_int, validate_block_param

logging.basicConfig()
JSONRPC_LOG = logging.getLogger("asynceth.jsonrpc.client")

# select which client to use
try:
    # if aiohttp is available, prefer that
    import aiohttp
    from asynceth.jsonrpc.aiohttp_client import HTTPClient
    JSONRPC_LOG.debug("using aiohttp jsonrpc client")
except:
    try:
        from asynceth.jsonrpc.tornado_client import HTTPClient
        JSONRPC_LOG.debug("using tornado jsonrpc client")
    except:
        raise ModuleNotFoundError("JsonRPCClient requires either aiohttp or tornado")

JSON_RPC_VERSION = "2.0"

def is_retryable_error(message):
    """common errors due to trying to access a block
    that hasn't been synced to the current node"""
    if message == "Unknown block number":
        return True
    if message == "One of the blocks specified in filter (fromBlock, toBlock or blockHash) cannot be found":
        return True
    return False

class JsonRPCClient:

    def __init__(self, url, *, should_retry=True, log=None,
                 max_clients=500, bulk_mode=False, connect_timeout=5.0, request_timeout=30.0,
                 client_cls=None, **kwargs):
        self._url = url
        self._max_clients = max_clients
        self._request_timeout = request_timeout
        self._connect_timeout = connect_timeout
        if client_cls:
            self._client_cls = client_cls
            self._httpclient = client_cls(max_clients=self._max_clients,
                                          connect_timeout=self._connect_timeout, **kwargs)
        else:
            self._client_cls = None
            self._httpclient = HTTPClient(max_clients=self._max_clients,
                                          connect_timeout=self._connect_timeout, **kwargs)
        self._client_kwargs = kwargs
        if log is None:
            self.log = JSONRPC_LOG
        else:
            self.log = log
        self.should_retry = should_retry
        self._bulk_mode = bulk_mode
        self._bulk_futures = {}
        self._bulk_data = []

    def _fetch(self, method, params=None, result_processor=None, request_timeout=None):

        if request_timeout is None:
            request_timeout = self._request_timeout

        id = random.randint(0, 1000000)

        if params is None:
            params = []

        data = {
            "jsonrpc": JSON_RPC_VERSION,
            "id": id,
            "method": method,
            "params": params
        }

        if self._bulk_mode is True:
            while id in self._bulk_futures:
                id = random.randint(0, 1000000)
                data['id'] = id
            self._bulk_data.append(data)
            future = asyncio.get_event_loop().create_future()
            self._bulk_futures[id] = (future, result_processor)
            return future

        return self._execute_single(data, result_processor, request_timeout=request_timeout)

    async def _execute_single(self, data, result_processor, request_timeout=None):
        if request_timeout is None:
            request_timeout = self._request_timeout
        # NOTE: letting errors fall through here for now as it means
        # there is something drastically wrong with the jsonrpc server
        # which means something probably needs to be fixed
        req_start = time.time()
        retries = 0
        while True:
            try:
                resp = await self._httpclient.fetch(
                    self._url,
                    method="POST",
                    body=data,
                    request_timeout=request_timeout
                )
            except Exception as e:
                self.log.error("Error in JsonRPCClient._fetch ({}, {}) \"{}\" attempt {}".format(
                    data['method'], data['params'], str(e), retries))
                retries += 1
                if self.should_retry and isinstance(e, HTTPError) and (e.status == 599 or e.status == 502):
                    # always retry after 599
                    pass
                elif not self.should_retry or time.time() - req_start >= request_timeout:
                    raise
                await asyncio.sleep(random.random())
                continue

            rval = await resp.json()

            # verify the id we got back is the same as what we passed
            if data['id'] != rval['id']:
                raise JsonRPCError(-1, "returned id was not the same as the inital request")

            if "error" in rval:
                # handle potential issues with the block number requested being too high because
                # the nodes haven't all synced to the current block yet
                # TODO: this is only supported by parity: geth returns "<nil>" when the block number if too high
                if 'message' in rval['error'] and is_retryable_error(rval['error']['message']):
                    retries += 1
                    if self.should_retry and time.time() - req_start < request_timeout:
                        await asyncio.sleep(random.random())
                        continue
                raise JsonRPCError(rval['id'], rval['error']['code'],
                                   rval['error']['message'],
                                   rval['error']['data'] if 'data' in rval['error'] else None)

            if result_processor:
                return result_processor(rval['result'])
            return rval['result']

    def close(self):
        return self._httpclient.close()

    def eth_getBalance(self, address, block="latest"):

        address = validate_hex_int(address)
        block = validate_block_param(block)

        return self._fetch("eth_getBalance", [address, block], parse_int)

    def eth_getTransactionCount(self, address, block="latest"):

        address = validate_hex_int(address)
        block = validate_block_param(block)

        return self._fetch("eth_getTransactionCount", [address, block], parse_int)

    def eth_estimateGas(self, source_address, target_address, **kwargs):

        source_address = validate_hex_int(source_address)
        hexkwargs = {"from": source_address}

        if target_address:
            target_address = validate_hex_int(target_address)
            hexkwargs["to"] = target_address

        for k, value in kwargs.items():
            if k == 'gasprice' or k == 'gas_price':
                k = 'gasPrice'
            hexkwargs[k] = validate_hex_int(value)
        if 'value' not in hexkwargs:
            hexkwargs['value'] = "0x0"
        return self._fetch("eth_estimateGas", [hexkwargs], parse_int)

    def eth_sendRawTransaction(self, tx):
        tx = validate_hex_int(tx)
        return self._fetch("eth_sendRawTransaction", [tx])

    def eth_getTransactionReceipt(self, tx):

        tx = validate_hex_int(tx)
        return self._fetch("eth_getTransactionReceipt", [tx])

    def eth_getTransactionByHash(self, tx):

        tx = validate_hex_int(tx)
        return self._fetch("eth_getTransactionByHash", [tx])

    def eth_blockNumber(self):

        return self._fetch("eth_blockNumber", [], parse_int)

    def eth_getBlockByNumber(self, number, with_transactions=True):

        number = validate_block_param(number)

        return self._fetch("eth_getBlockByNumber", [number, with_transactions])

    def eth_newFilter(self, *, fromBlock=None, toBlock=None, address=None, topics=None):

        kwargs = {}
        if fromBlock:
            kwargs['fromBlock'] = validate_block_param(fromBlock)
        if toBlock:
            kwargs['toBlock'] = validate_block_param(toBlock)
        if address:
            kwargs['address'] = validate_hex_int(address)
        if topics:
            if not isinstance(topics, list):
                raise TypeError("topics must be an array of DATA")
            kwargs['topics'] = [None if i is None else validate_hex_int(i, 32) for i in topics]

        return self._fetch("eth_newFilter", [kwargs])

    def eth_newPendingTransactionFilter(self):

        return self._fetch("eth_newPendingTransactionFilter", [])

    def eth_newBlockFilter(self):

        return self._fetch("eth_newBlockFilter", [])

    def eth_getFilterChanges(self, filter_id):

        return self._fetch("eth_getFilterChanges", [filter_id])

    def eth_getFilterLogs(self, filter_id):

        return self._fetch("eth_getFilterLogs", [filter_id])

    def eth_uninstallFilter(self, filter_id):

        return self._fetch("eth_uninstallFilter", [filter_id])

    def eth_getCode(self, address, block="latest"):

        address = validate_hex_int(address)
        block = validate_block_param(block)
        return self._fetch("eth_getCode", [address, block])

    async def _eth_getLogs_with_block_number_validation(self, kwargs):
        req_start = time.time()
        from_block = parse_int(kwargs.get('fromBlock', None))
        to_block = parse_int(kwargs.get('toBlock', None))
        while True:
            bulk = self.bulk()
            bn_future = bulk.eth_blockNumber()
            lg_future = bulk._fetch("eth_getLogs", [kwargs])
            await bulk.execute()
            bn = bn_future.result()
            if (from_block and bn < from_block) or (to_block and bn < to_block):
                if self.should_retry and time.time() - req_start < self._request_timeout:
                    await asyncio.sleep(random.random())
                    continue
                raise JsonRPCError(None, -32000, "Unknown block number", None)
            return lg_future.result()

    def eth_getLogs(self, fromBlock=None, toBlock=None, address=None, topics=None, validate_block_number=True):
        """validate_block_number (default True), if True will also check the node's
        current blockNumber and make sure it is not lower than either the fromBlock
        or toBlock arguments"""

        kwargs = {}
        if fromBlock:
            kwargs['fromBlock'] = validate_block_param(fromBlock)
        if toBlock:
            kwargs['toBlock'] = validate_block_param(toBlock)
        if address:
            kwargs['address'] = validate_hex_int(address)
        if topics:
            # validate topics
            if not isinstance(topics, list):
                raise TypeError("topics must be an array of DATA")
            for topic in topics:
                if isinstance(topic, list):
                    if not all(validate_hex_int(t, 32) for t in topic if t is not None):
                        raise TypeError("topics must be an array of DATA")
                else:
                    if topic is not None and not validate_hex_int(topic):
                        raise TypeError("topics must be an array of DATA")
            kwargs['topics'] = topics

        if validate_block_number and (fromBlock or toBlock):
            return self._eth_getLogs_with_block_number_validation(kwargs)
        else:
            return self._fetch("eth_getLogs", [kwargs])

    def eth_call(self, *, to_address, from_address=None, gas=None, gasprice=None, value=None, data=None, block="latest", result_processor=None):

        to_address = validate_hex_int(to_address)
        block = validate_block_param(block)

        callobj = {"to": to_address}
        if from_address:
            callobj['from'] = validate_hex_int(from_address)
        if gas:
            callobj['gas'] = validate_hex_int(gas)
        if gasprice:
            callobj['gasPrice'] = validate_hex_int(gasprice)
        if value:
            callobj['value'] = validate_hex_int(value)
        if data:
            callobj['data'] = validate_hex_int(data)

        return self._fetch("eth_call", [callobj, block], result_processor)

    def eth_gasPrice(self):

        return self._fetch("eth_gasPrice", [], parse_int)

    def trace_transaction(self, transaction_hash):

        return self._fetch("trace_transaction", [transaction_hash])

    def trace_get(self, transaction_hash, *positions):

        return self._fetch("trace_get", [transaction_hash, positions])

    def trace_replayTransaction(self, transaction_hash, *, vmTrace=False, trace=True, stateDiff=False):

        trace_type = []
        if vmTrace:
            trace_type.append('vmTrace')
        if trace:
            trace_type.append('trace')
        if stateDiff:
            trace_type.append('stateDiff')

        return self._fetch("trace_replayTransaction", [transaction_hash, trace_type])

    def debug_traceTransaction(self, transaction_hash, *, disableStorage=None, disableMemory=None, disableStack=None,
                               fullStorage=None, tracer=None, timeout=None):
        kwargs = {}
        if disableStorage is not None:
            kwargs['disableStorage'] = disableStorage
        if disableMemory is not None:
            kwargs['disableMemory'] = disableMemory
        if disableStack is not None:
            kwargs['disableStack'] = disableStack
        if tracer is not None:
            kwargs['tracer'] = tracer
        if timeout is not None:
            kwargs['timeout'] = str(timeout)

        return self._fetch("debug_traceTransaction", [transaction_hash, kwargs])

    def web3_clientVersion(self):

        return self._fetch("web3_clientVersion", [])

    def net_version(self):

        return self._fetch("net_version", [])

    def bulk(self):
        return JsonRPCClient(self._url, should_retry=self.should_retry, log=self.log,
                             max_clients=self._max_clients, bulk_mode=True,
                             request_timeout=self._request_timeout,
                             connect_timeout=self._connect_timeout,
                             client_cls=self._client_cls, **self._client_kwargs)

    async def execute(self):
        if not self._bulk_mode:
            raise Exception("No Bulk request started")
        if len(self._bulk_data) == 0:
            return []

        data = self._bulk_data[:]
        self._bulk_data = []
        futures = self._bulk_futures.copy()
        self._bulk_futures = {}
        req_start = time.time()

        retries = 0
        while True:
            try:
                resp = await self._httpclient.fetch(
                    self._url,
                    method="POST",
                    body=data,
                    request_timeout=60.0 # higher request timeout than other operations
                )
            except Exception as e:
                self.log.error("Error in JsonRPCClient.execute: retry {}".format(retries))
                retries += 1
                if self.should_retry and isinstance(e, HTTPError) and (e.status == 599 or e.status == 502):
                    # always retry after 599
                    pass
                elif not self.should_retry or time.time() - req_start >= self._request_timeout:
                    # give up after the request timeout
                    raise
                await asyncio.sleep(random.random())
                continue
            break

        rvals = await resp.json()

        results = []
        for rval in rvals:
            if 'id' not in rval:
                continue
            future, result_processor = futures.pop(rval['id'], (None, None))
            if future is None:
                self.log.warning("Got unexpected id in jsonrpc bulk response")
                continue
            if "error" in rval:
                future.set_exception(JsonRPCError(rval['id'], rval['error']['code'], rval['error']['message'], rval['error']['data'] if 'data' in rval['error'] else None))
                result = None
            else:
                if result_processor:
                    result = result_processor(rval['result'])
                else:
                    result = rval['result']
                future.set_result(result)
            results.append(result)

        if len(futures):
            self.log.warning("Found some unprocessed requests in bulk jsonrpc request")
            for future, result_processor in futures:
                future.set_exception(Exception("Unexpectedly missing result"))

        return results
