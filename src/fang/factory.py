import base64
import json
import os
import traceback

from werkzeug.exceptions import HTTPException

from fang.entities import BaseEntity
from .wrappers import Response, Request


def convert_string(string: str, typing: type):
    if typing is int or typing is float or typing is bool:
        return typing(string)
    return string


def normalize(item):
    if isinstance(item, dict):
        for k, v in item.items():
            item[k] = normalize(v)
    elif isinstance(item, list):
        transformed = []
        for v in item:
            transformed.append(normalize(v))
        item = transformed
    elif isinstance(item, tuple):
        transformed = []
        for v in item:
            transformed.append(normalize(v))
        item = tuple(transformed)
    elif isinstance(item, BaseEntity):
        item = normalize(item.to_dict())
    elif isinstance(item, bytes):
        item = base64.b64encode(item).decode('utf-8')
    return item


def make_response(
        response=None,
        status=200,
        mimetype=None,
        headers=None,
        content_type=None,
        direct_passthrough=False,
) -> Response:
    original_response = response
    if response is not None and not isinstance(response, str) and mimetype is None:
        normalized = normalize(response)
        response = json.dumps(normalized)
        mimetype = 'application/json'
    resp = Response(
        response=response,
        status=status,
        mimetype=mimetype,
        headers=headers,
        content_type=content_type,
        direct_passthrough=direct_passthrough
    )
    setattr(resp, 'original_response', original_response)
    return resp


base_dir = os.path.dirname(os.path.dirname(__file__))


def make_error_response(e: Exception, request: Request, status: int = None):
    if isinstance(e, HTTPException):
        if e.response:
            message = e.response
        else:
            message = str(e)
        if status is None:
            status = e.code
    else:
        message = str(e)
    data = {
        "name": e.__class__.__name__,
        "message": message
    }
    if status is None:
        status = 500
    if status == 500 and request is not None:
        data['request'] = {
            "path": request.path,
            "query": request.query,
            "body": request.body
        }
        tb = []
        for fs in traceback.extract_tb(e.__traceback__):
            tb.append((fs.filename[len(base_dir) + 1:], fs.lineno, fs.line))
        data['traceback'] = tb
    return make_response({'error': data}, status=status)
