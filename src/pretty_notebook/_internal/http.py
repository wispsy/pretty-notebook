"""Finite, owned Requ calls for notebook publication and account operations."""

import requ
from requ import ConnectionError, HTTPError, RequestException, Timeout
from requ.requests import Response

# Cover 10 MiB images plus multipart framing and 2M-character JSON pages.
MAX_REQUEST_BYTES = 16 * 1024 * 1024
MAX_RESPONSE_BYTES = 64 * 1024 * 1024


def request(method, url, **kwargs):
    """Return owned response bytes and close the transport on every path."""
    timeout = kwargs.pop('timeout', (5, 30))
    with requ.Session(timeout=timeout, max_request_bytes=MAX_REQUEST_BYTES,
                      max_bytes=MAX_RESPONSE_BYTES, trust_env=False) as session:
        return session.request(method, url, **kwargs)


def get(url, **kwargs):
    return request('GET', url, **kwargs)


def post(url, **kwargs):
    return request('POST', url, **kwargs)


def put(url, **kwargs):
    return request('PUT', url, **kwargs)


def delete(url, **kwargs):
    return request('DELETE', url, **kwargs)


__all__ = ['get', 'post', 'put', 'delete', 'request', 'Response',
           'ConnectionError', 'HTTPError', 'RequestException', 'Timeout']
