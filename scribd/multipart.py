"""
Handles posting of HTTP multipart/form-data requests.

Based on code posted by Wade Leftwich on:
http://code.activestate.com/recipes/146306/

with modifications to use HTTPConnection class by Chris Hoke

and final touches by me, Arkadiusz Wahlig.
"""

import sys
import httplib
import mimetypes
from random import randrange


def post_multipart(host, selector, fields=(), headers=None, port=None):
    """Posts a multipart/form-data request to an HTTP host/port.
    
    Parameters:
      host
        HTTP host name.
      selector
        HTTP request path.
      fields
        POST fields. A sequence of (name, value) tuples where "name" is the
        field name and "value" may be either a string or a (data, name)
        tuple in which case the "data" will be sent as a file of name "name".
      headers
        A mapping of additional HTTP headers.
      port
        TCP/IP port. Defaults to 80.
        
    Returns:
        A httplib.HTTPResponse object.
    """
    boundary = '----------%s--%s----------' % \
        (randrange(sys.maxint), randrange(sys.maxint))
    if headers is None:
        headers = {}
    headers['Content-Type'] = 'multipart/form-data; boundary=%s' % boundary
    body = encode_multipart_formdata(fields, boundary)
    h = httplib.HTTPConnection(host, port)
    h.request('POST', selector, body, headers)
    return h.getresponse()


def encode_multipart_formdata(fields, boundary):
    lines = []
    for key, value in fields:
        lines.append('--' + boundary)
        if isinstance(value, tuple): # file
            data, name = value
            ctype = mimetypes.guess_type(name)[0] or 'application/octet-stream'
            lines.append('Content-Disposition: form-data; name="%s"; filename="%s"' % (key, name))
            lines.append('Content-Type: %s' % ctype)
            lines.append('')
            lines.append(data)
        elif isinstance(value, str): # str
            lines.append('Content-Disposition: form-data; name="%s"' % key)
            lines.append('')
            lines.append(value)
        else:
            raise TypeError('value must be a tuple or str, not %s' % type(value).__name__)
    lines.append('--' + boundary + '--')
    return '\r\n'.join(lines)
