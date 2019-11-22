import inspect
from abc import ABC, abstractmethod
from logging import getLogger
from typing import Any, Dict, Callable

from werkzeug import Request, Response
from werkzeug.exceptions import BadRequest
from werkzeug.routing import Map, Rule, Submount, RequestRedirect

from .entities import db, sync_tables, BaseEntity
from .factory import make_response, make_error_response, convert_string
from .wrappers import Response, Request, Query, Body, Params, Middleware, Files


class Routable(ABC):

    def route(self, path, methods=('GET',), func=None):
        if isinstance(methods, str):
            methods = [methods]
        if func:
            self._route(path, methods, func)
        else:
            def decorate(to_decorate):
                self._route(path, methods, to_decorate)
                return to_decorate

            return decorate

    @abstractmethod
    def _route(self, path, methods, func):
        pass

    @abstractmethod
    def add(self, prefix: str, collection) -> None:
        pass


class Blueprint(Routable):

    def __init__(self):
        self.mapping = []

    def _route(self, path, methods, func):
        self.mapping.append(Rule(path, endpoint=Endpoint(func), methods=methods))

    def add(self, prefix: str, blueprint: 'Blueprint') -> None:
        if not prefix.startswith('/'):
            prefix = '/' + prefix
        self.mapping.append(Submount(prefix, blueprint.mapping))


class EndpointContext:
    query_methods = ('GET', 'HEAD')
    body_methods = ('POST', 'PUT', 'PATCH', 'DELETE')

    def __init__(self, request: Request):
        self.injectable: Dict[type, Callable[[], object]] = {
            Body: lambda: request.body,
            Query: lambda: request.query,
            Params: lambda: request.params,
            Request: lambda: request,
            Files: lambda: Files(request)
        }
        self.buckets = [request.params]
        if request.method in self.query_methods:
            self.buckets.append(request.query)
        elif request.method in self.body_methods:
            self.buckets.append(request.body)

    def has_item(self, clz: type):
        if clz in self.injectable:
            return True
        return False

    def get_item(self, clz: type):
        return self.injectable[clz]()

    def get(self, name: str, typing: type):
        value = None
        bucket = None
        for bucket in self.buckets:
            if name in bucket:
                value = bucket[name]
                break
        if typing is not None and value is not None:
            if isinstance(bucket, Params):
                try:
                    value = convert_string(value, typing)
                except ValueError:
                    raise BadRequest(
                        response=f"Invalid type '{value.__class__.__name__}', expected '{typing.__name__}'")
            else:
                if not isinstance(value, typing):
                    raise BadRequest(
                        response=f"Invalid type {value.__class__.__name__} for parameter '{name}', expected {typing.__name__}")
                if isinstance(value, dict) and issubclass(typing, BaseEntity):
                    print('asd', value)
        return value


class Endpoint:

    def __init__(self, func):
        self.func = func

    def invoke(self, request: Request) -> Any:
        kwargs = self.build_args(request)

        result = self.func(**kwargs)
        return self.parse_result(result)

    @staticmethod
    def parse_result(result):
        if result is None:
            return Response()
        else:
            if isinstance(result, Response):
                return result
            else:
                return make_response(result)

    def build_args(self, request: Request):
        context = EndpointContext(request)
        argspec = inspect.getfullargspec(self.func)
        args = argspec.args + argspec.kwonlyargs
        kwargs = {}

        for name, typing in argspec.annotations.items():
            if context.has_item(typing):
                args.remove(name)
                kwargs[name] = context.get_item(typing)

        for name in args:
            value = context.get(name, argspec.annotations.get(name, None))
            if value:
                kwargs[name] = value

        return kwargs


class Application(Routable):

    def __init__(self, name):
        self.name = name
        self.dispatch = self._dispatch
        self.mapping = Map()
        self.error_handler = self.handle_error
        self.logger = getLogger(name)

    @staticmethod
    def database(database):
        db.initialize(database)
        sync_tables()

    def use_blueprint(self, prefix: str, collection: Blueprint) -> None:
        if not prefix.startswith('/'):
            prefix = '/' + prefix
        self.mapping.add(Submount(prefix, collection.mapping))

    def _route(self, path, methods, func):
        self.mapping.add(Rule(path, endpoint=Endpoint(func), methods=methods))

    def use_middleware(self, middleware: Middleware):
        next_dispatch = self._dispatch
        self.dispatch = lambda x: middleware(x, next_dispatch)

    @staticmethod
    def _dispatch(request: Request) -> Response:
        return request.endpoint.invoke(request)

    def handle_error(self, e: Exception, request: Request):
        err_response = make_error_response(e, request)
        original = err_response.original_response
        if err_response.status_code == 500:
            self.logger.error('Error when handling request', exc_info=e, extra=original)
        return err_response

    def __call__(self, environ, start_response):
        request = None
        try:
            request = Request(environ, self.mapping)
            response = self.dispatch(request)
            return response(environ, start_response)
        except RequestRedirect as e:
            return Response(status=e.code, headers={'Location': e.new_url})(environ, start_response)
        except Exception as e:
            return self.error_handler(e, request)(environ, start_response)
