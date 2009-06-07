'''Handles posting of HTTP multipart/form-data requests.

Based on code posted by Wade Leftwich on:
http://code.activestate.com/recipes/146306/

with modifications to use HTTPConnection class by Chris Hoke

and final touches by me, Arkadiusz Wahlig.
'''

import httplib
import mimetypes


def post_multipart(host, selector, fields=(), headers=None, port=80):
    '''Posts a multipart/form-data request to an HTTP host/port.
    
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
        
    Returns:
        A httplib.HTTPResponse object.
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
    BOUNDARY = '----------ThIs_Is_tHe_bouNdaRY_$'
    L = []
    for key, value in fields:
        if isinstance(value, tuple): # file
            data, name = value
            L.append('--' + BOUNDARY)
            L.append('Content-Disposition: form-data; name="%s"; filename="%s"' % (key, name))
            L.append('Content-Type: %s' % get_content_type(name))
            L.append('')
            L.append(data)
        elif isinstance(value, str): # str
            L.append('--' + BOUNDARY)
            L.append('Content-Disposition: form-data; name="%s"' % key)
            L.append('')
            L.append(value)
        else:
            raise TypeError('value must be a file or str, not %s' % type(value).__name__)
    L.append('--' + BOUNDARY + '--')
    L.append('')
    body = '\r\n'.join(L)
    content_type = 'multipart/form-data; boundary=%s' % BOUNDARY
    return content_type, body


def get_content_type(filename):
    '''Guesses the content type based on a filename.
    '''
    return mimetypes.guess_type(filename)[0] or 'application/octet-stream'
