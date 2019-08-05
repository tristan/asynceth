import aiohttp
import asyncio
import weakref

from asynceth.jsonrpc.errors import HTTPError

class HTTPClient:

    @classmethod
    def _async_clients(cls):
        attr_name = '_async_client_dict_' + cls.__name__
        if not hasattr(cls, attr_name):
            setattr(cls, attr_name, weakref.WeakKeyDictionary())
        return getattr(cls, attr_name)

    def __new__(cls, force_instance=False, **kwargs):
        loop = asyncio.get_event_loop()
        if force_instance:
            instance_cache = None
        else:
            instance_cache = cls._async_clients()
        if instance_cache is not None and loop in instance_cache:
            return instance_cache[loop]
        instance = super().__new__(cls)
        # Make sure the instance knows which cache to remove itself from.
        instance._loop = loop
        instance._instance_cache = instance_cache
        if instance_cache is not None:
            instance_cache[instance._loop] = instance
        instance.initialise(**kwargs)
        return instance

    def initialise(self, *, max_clients=100, connect_timeout=None, verify_ssl=True):
        connector = aiohttp.TCPConnector(
            limit=max_clients)
        self._verify_ssl = verify_ssl
        timeout = aiohttp.ClientTimeout(connect=connect_timeout)
        self._session = aiohttp.ClientSession(connector=connector, timeout=timeout)

    async def fetch(self, url, *, method="GET", headers=None, body=None, request_timeout=None):
        fn = getattr(self._session, method.lower())
        kwargs = {}
        if isinstance(body, (dict, list)) and (headers is None or 'Content-Type' not in headers):
            kwargs['json'] = body
        else:
            kwargs['data'] = body
        if request_timeout:
            kwargs['timeout'] = request_timeout
        try:
            resp = await fn(url, headers=headers, ssl=self._verify_ssl, **kwargs)
            if resp.status < 200 or resp.status >= 300:
                raise HTTPError(resp.status, message=resp.reason)
            return resp
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            error = e
        # outside of the except block to avoid rethrow error message
        raise HTTPError(599, message=str(error))

    async def close(self):
        await self._session.close()
        if self._instance_cache is not None:
            del self._instance_cache[self._loop]
