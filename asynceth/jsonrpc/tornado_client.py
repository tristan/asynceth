import tornado.escape

try:
    # prefer curl if pycurl is available
    import pycurl
    from tornado.curl_httpclient import CurlAsyncHTTPClient as AsyncHTTPClient
except ModuleNotFoundError:
    from tornado.httpclient import AsyncHTTPClient

from asynceth.jsonrpc.errors import HTTPError

class HTTPResponse:
    def __init__(self, status, body):
        self.status = status
        self.body = body

    async def json(self, *, encoding=None, loads=tornado.escape.json_decode, content_type='application/json'):
        return loads(self.body)

class HTTPClient:

    def __init__(self, *, max_clients=100, connect_timeout=20.0, verify_ssl=True, **kwargs):
        self._httpclient = AsyncHTTPClient(max_clients=max_clients, **kwargs)
        self._connect_timeout = connect_timeout
        self._verify_ssl = verify_ssl

    async def fetch(self, url, *, method="GET", headers=None, body=None, request_timeout=30.0):
        if isinstance(body, (dict, list)):
            if headers is None:
                headers = {'Content-Type': "application/json"}
            elif 'Content-Type' not in headers:
                headers['Content-Type'] = "application/json"
            body = tornado.escape.json_encode(body)
        resp = await self._httpclient.fetch(url,
                                            method=method,
                                            headers=headers,
                                            body=body,
                                            validate_cert=self._verify_ssl,
                                            request_timeout=request_timeout,
                                            connect_timeout=self._connect_timeout,
                                            raise_error=False)
        if resp.code < 200 or resp.code >= 300:
            raise HTTPError(resp.code, message=resp.reason)
        return HTTPResponse(resp.code, resp.body)

    async def close(self):
        self._httpclient.close()
