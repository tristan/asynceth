from http.client import responses

class HTTPError(Exception):
    def __init__(self, status, message=None):
        self.status = status
        self.message = message or responses.get(status, "Unknown")
        super().__init__(status, message)

    def __str__(self):
        return "HTTP %d: %s" % (self.status, self.message)

class JsonRPCError(Exception):
    def __init__(self, request_id, code, message, data, is_notification=False):
        super().__init__(message)
        self.request_id = request_id
        self.code = code
        self.message = message
        self._data = data
        self.is_notification = is_notification

    def format(self, request=None):
        if request:
            if 'id' not in request:
                self.is_notification = True
            else:
                self.request_id = request['id']
        # if the request was a notification, return nothing
        if self.is_notification:
            return None
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": self.code,
                "message": self.message,
                "data": self._data,
            },
            "id": self.request_id
        }

    @property
    def data(self):
        if self._data:
            return self._data
        return {'message': self.message}

    def __str__(self):
        return "Json RPC Error ({}): {}{}".format(
            self.code, self.message,
            " {}".format(self._data) if self._data else "")

class JsonRPCInvalidParamsError(JsonRPCError):
    def __init__(self, *, request=None, data=None):
        super().__init__(request.get('id') if request else None,
                         -32602, "Invalid params", data,
                         'id' not in request if request else False)

class JsonRPCInternalError(JsonRPCError):
    def __init__(self, *, request=None, data=None):
        super().__init__(request.get('id') if request else None,
                         -32603, "Internal Error", data,
                         'id' not in request if request else False)
