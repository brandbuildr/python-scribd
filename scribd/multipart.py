'''Handles posting of HTTP multipart/form-data requests.

Based on code posted by Wade Leftwich on:
http://code.activestate.com/recipes/146306/

with modifications to use HTTPConnection class by Chris Hoke

and final touches by me, Arkadiusz Wahlig.
'''

import httplib
import mimetypes


BOUNDARY = '--$$$--$$-ThIs_Is_tHe_bouNdaRY-----$-----$$-'


def post_multipart(host, selector, fields=(), headers=None, port=None):
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
    body = encode_multipart_formdata(fields)
    hdrs = {'Content-Type': 'multipart/form-data; boundary=%s' % BOUNDARY,
            'Content-Length': str(len(body))}
    if headers is not None:
        hdrs.update(headers)
    h = httplib.HTTPConnection(host, port)
    h.request('POST', selector, body, hdrs)
    return h.getresponse()


def encode_multipart_formdata(fields):
    lines = []
    for key, value in fields:
        if isinstance(value, tuple): # file
            data, name = value
            lines.append('--' + BOUNDARY)
            lines.append('Content-Disposition: form-data; name="%s"; filename="%s"' % (key, name))
            lines.append('Content-Type: %s' % get_content_type(name))
            lines.append('')
            lines.append(data)
        elif isinstance(value, str): # str
            lines.append('--' + BOUNDARY)
            lines.append('Content-Disposition: form-data; name="%s"' % key)
            lines.append('')
            lines.append(value)
        else:
            raise TypeError('value must be a tuple or str, not %s' % type(value).__name__)
    lines.append('--' + BOUNDARY + '--')
    lines.append('')
    return '\r\n'.join(lines)


def get_content_type(filename):
    '''Guesses the content type based on a filename.
    '''
    return mimetypes.guess_type(filename)[0] or 'application/octet-stream'
