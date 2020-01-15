import json
from typing import Callable, Union

import werkzeug
from werkzeug.routing import Map


class Params(dict):
    pass


Body = Union[dict, list, str, int, float]


class Query(dict):
    pass


class Response(werkzeug.Response):
    pass


class Request(werkzeug.Request):

    def __init__(self, environ, mapping: Map):
        super().__init__(environ)
        self.query = Query(self.args)
        if self.mimetype == 'application/json':
            self.body = json.loads(self.data.decode('utf-8'))
        else:
            self.body = None
        self.endpoint, value = mapping.bind_to_environ(environ).match()
        self.params = Params(value)


class Files:

    def __init__(self, request: Request):
        self.items = []
        for name, item in request.files.items():
            self.items.append((name, item))


Respond = Callable[[Request], Response]
Middleware = Callable[[Request, Respond], Response]

__all__ = [
    'Request',
    'Response',
    'Params',
    'Body',
    'Query',
    'Respond',
    'Middleware',
    'Files',
]
