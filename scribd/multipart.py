'''Handles posting of HTTP multipart/form-data requests.

Based on code posted by Wade Leftwich on:
http://code.activestate.com/recipes/146306/

with modifications to use HTTPConnection class by Chris Hoke

and final touches by me, Arkadiusz Wahlig.
'''

import httplib
import mimetypes
import os


def post_multipart(host, selector, fields=(), headers=None, port=80):
    '''Posts a multipart/form-data request to an HTTP host/port.
    fields is a sequence of (name, value) elements representing the form
    fields where name is a string and value may be a string or a file-a-like
    object providing a read() method and a name attribute.
    headers is a dictionary of additional HTTP headers.
    Returns the httplib.HTTPResponse object.
    '''
    content_type, body = encode_multipart_formdata(fields)
    h = httplib.HTTPConnection(host, port)
    hdrs = {'Content-Type': content_type,
            'Content-Length': str(len(body))}
    if headers is not None:
        hdrs.update(headers)
    h.request('POST', selector, body, hdrs)
    return h.getresponse()


def encode_multipart_formdata(fields):
    '''fields is an iterable of (name, value) elements representing the form
    fields where name is a string and value may be a string or a file-a-like
    object providing a read() method and a name attribute.
    Returns a (content_type, encoded_body) tuple.
    '''
    BOUNDARY = '----------ThIs_Is_tHe_bouNdaRY_$'
    CRLF = '\r\n'
    L = []
    for key, value in fields:
        if hasattr(value, 'read') and hasattr(value, 'name'): # file
            filename = os.path.basename(value.name)
            L.append('--' + BOUNDARY)
            L.append('Content-Disposition: form-data; name="%s"; filename="%s"' % (key, filename))
            L.append('Content-Type: %s' % get_content_type(filename))
            L.append('')
            L.append(value.read())
        elif isinstance(value, str): # str
            L.append('--' + BOUNDARY)
            L.append('Content-Disposition: form-data; name="%s"' % key)
            L.append('')
            L.append(value)
        else:
            raise TypeError('value must be a file or str, not %s' % type(value).__name__)
    L.append('--' + BOUNDARY + '--')
    L.append('')
    body = CRLF.join(L)
    content_type = 'multipart/form-data; boundary=%s' % BOUNDARY
    return content_type, body


def get_content_type(filename):
    '''Guesses the content type based on a filename.
    '''
    return mimetypes.guess_type(filename)[0] or 'application/octet-stream'
