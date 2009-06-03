'''Scribd.com client library.

Copyright (c) 2009 Arkadiusz Wahlig
<arkadiusz.wahlig@gmail.com>
'''

import sys
import httplib
import urllib
import logging
from xml.dom.minidom import parse
if sys.version_info >= (2, 5):
    from hashlib import md5
else:
    from md5 import md5

from multipart import post_multipart


__author__ = 'Arkadiusz Wahlig'
__version__ = '0.9.0'

HOST = 'api.scribd.com'
PORT = 80
REQUEST_PATH = '/api'

key = ''
secret = ''


class NullHandler(logging.Handler):
    def emit(self, record):
        pass


class MalformedResponseError(Exception):
    def __init__(self, errstr):
        Exception.__init__(self, str(errstr))     
    

class NotReadyError(Exception):
    def __init__(self, errstr):
        Exception.__init__(self, str(errstr))     
    
    
class ResponseError(Exception):
    def __init__(self, errno, errstr):
        Exception.__init__(self, int(errno), str(errstr))

    def __str__(self):
        return '[Errno %d] %s' % (self[0], self[1]) 


class Resource(object):
    _fields = {}
    
    def __init__(self, tag=None):
        self._values = {}
        if tag is None:
            self._changed_fields()
        else:
            self._set_from_tag(tag)

    def _send_request(self, method, **fields):
        return send_request(method, **fields)

    def _set_from_tag(self, tag):
        for sub in tag:
            if sub.value is not None and not hasattr(self, sub.name):
                value = self._fields.get(sub.name, unicode)(sub.value)
                setattr(self, sub.name, value)
        self._changed_fields()

    def _changed_fields(self):
        fields = {}
        for name in self._fields.keys():
            if getattr(self, name, None) != self._values.get(name, None):
                fields[name] = getattr(self, name, None)
        if fields:
            self._values = {}
            for name in self._fields.keys():
                self._values[name] = getattr(self, name, None)
        return fields

    def __repr__(self):
        return '<%s.%s object with id=%s>' % (self.__class__.__module__,
            self.__class__.__name__, repr(self.id))

    def __eq__(self, other):
        if isinstance(other, Resource):
            return (self.id == other.id)
        return object.__eq__(self, other)

    def _get_id(self):
        return ''

    id = property(_get_id)


class User(Resource):
    _fields = {'session_key': str,
               'user_id': str,
               'username': str,
               'name': unicode}
               
    def __init__(self, tag=None):
        Resource.__init__(self, tag)
        if tag is None:
            # Default API user. Set all attributes to empty strings.
            # Because session_key is one of them, it will be omitted
            # from requests.
            for name in self._fields.keys():
                setattr(self, name, '')

    def _send_request(self, method, **fields):
        if self.session_key:
            # Add the session_key field to limit the executed
            # method to the current user.
            fields['session_key'] = self.session_key
        return Resource._send_request(self, method, **fields)

    def all(self, **kwargs):
        tag = self._send_request('docs.getList', **kwargs)
        return [Document(result, self) for result in tag.get('resultset')]

    def xall(self, **kwargs):
        while True:
            tag = self._send_request('docs.getList', **kwargs)
            results = tag.get('resultset')
            if len(results) == 0:
                break
            for result in results:
                yield Document(result, self)
            if len(results) < kwargs.get('limit', 0):
                break
            kwargs['offset'] = kwargs.get('offset', 0) + len(results)
        
    def get(self, doc_id):
        tag = self._send_request('docs.getSettings', doc_id=doc_id)
        return Document(tag, self)
        
    def find(self, query, **kwargs):
        kwargs['num_results'] = kwargs.pop('limit', None)
        kwargs['num_start'] = kwargs.pop('offset', None)
        tag = self._send_request('docs.search', query=query, **kwargs)
        return [Document(result, self) for result in tag.get('result_set')]

    def xfind(self, query, **kwargs):
        kwargs['num_results'] = kwargs.pop('limit', None)
        kwargs['num_start'] = kwargs.pop('offset', None)
        while True:
            tag = self._send_request('docs.search', query=query, **kwargs)
            results = tag.get('result_set')
            for result in results:
                yield Document(result, self)
            kwargs['num_start'] = int(results.firstResultPosition) + \
                                   int(results.totalResultsReturned)
            if kwargs['num_start'] >= int(results.totalResultsAvailable):
                break

    def upload(self, file, **kwargs):
        if isinstance(file, str):
            tag = self._send_request('docs.uploadFromUrl', url=file, **kwargs)
        else:
            tag = self._send_request('docs.upload', file=file, **kwargs)
        doc = Document(tag, self)
        doc.load()
        return doc

    def get_autologin_url(self, next_url, **kwargs):
        tag = self._send_request('user.getAutoSigninUrl', next_url=next_url,
                           **kwargs)
        return str(tag.get('url').value)

    def _get_id(self):
        return self.user_id

    id = property(_get_id)


class Document(Resource):
    _fields = {'doc_id': str,
               'access_key': str,
               'secret_password': str,
               'title': unicode,
               'description': unicode,
               'thumbnail_url' : str,
               'conversion_status': str,
               'page_count': int,
               'access': str,
               'license': str,
               'tags': unicode,
               'show_ads': str,
               'author': unicode,
               'publisher': unicode,
               'when_published': str,
               'edition': unicode}

    def __init__(self, tag, owner):
        Resource.__init__(self, tag)
        self.owner = owner
        
    def _send_request(self, method, **fields):
        if isinstance(self.owner, User):
            return self.owner._send_request(method, **fields)
        elif isinstance(self.owner, str):
            fields['my_user_id'] = self.owner
            return Resource._send_request(self, method, **fields)
        raise ValueError('owner must be a User object or str, not %s' %
                          type(self.owner).__name__)
        
    def get_conversion_status(self):
        tag = self._send_request('docs.getConversionStatus', doc_id=self.doc_id)
        self.conversion_status = str(tag.get('conversion_status').value)
        return self.conversion_status
        
    def delete(self):
        tag = self._send_request('docs.delete', doc_id=self.doc_id)
        return (tag.stat == 'ok')
        
    def get_url(self, format='original'):
        tag = self._send_request('docs.getDownloadUrl', doc_id=self.doc_id,
                           doc_type=format)
        return str(tag.get('download_link').value)
        
    def load(self):
        tag = self._send_request('docs.getSettings', doc_id=self.doc_id)
        self._set_from_tag(tag)
        
    def save(self):
        fields = self._changed_fields()
        if fields:
            self._send_request('docs.changeSettings', doc_ids=self.doc_id,
                               **fields)
            return True
        return False

    def _get_id(self):
        return self.doc_id

    id = property(_get_id)


class Tag(object):
    def __init__(self, element):
        self.name = str(element.tagName)
        self.value = None
        nodes = element.childNodes
        if len(nodes) == 1 and nodes[0].nodeType == element.TEXT_NODE:
            self.value = nodes[0].data.strip()
            self._nodes = []
        else:
            self._nodes = [node for node in nodes if node.nodeType != element.TEXT_NODE]
        if len(self._nodes) == 1 and self._nodes[0].nodeType == \
                                     element.CDATA_SECTION_NODE:
            self.value = self._nodes[0].data.strip()
            self._nodes = []
        for name, value in element.attributes.items():
            if not hasattr(self, name):
                setattr(self, name, value)
        
    def index(self, name):
        for i, c in enumerate(self._nodes):
            if str(c.tagName) == name:
                return i
        raise IndexError('%s is not in the sub-tags' % name)
        
    def get(self, name):
        try:
            return Tag(self._nodes[self.index(name)])
        except IndexError:
            raise KeyError('%s is not in the sub-tags' % name)
        
    def __getitem__(self, i):
        return Tag(self._nodes[i])
        
    def __len__(self):
        return len(self._nodes)
        
    def __repr__(self):
        value = ''
        if self.value is not None:
            value = ', value=%s' % repr(self.value)
        return '<%s.%s object at 0x%x with name=%s%s>' % (self.__class__.__module__,
               self.__class__.__name__, id(self), repr(self.name), value)
    
    
def send_request(method, **fields):
    if not key or not secret:
        raise NotReadyError('configure api key and secret key first')
    if not method:
        raise ValueError('method must not be empty')
    
    fields['method'] = method
    fields['api_key'] = key
    
    sign_fields = {}
    for k, v in fields.items():
        if v:
            if isinstance(v, unicode):
                v = v.encode('utf8')
            elif isinstance(v, (int, long)):
                v = str(v)
            sign_fields[k] = v
    fields = sign_fields.copy()
            
    deb_fields = fields.copy()
    del deb_fields['method'], deb_fields['api_key']
    logger.debug('Request: %s(%s)', method,
                 ', '.join('%s=%s' % (k, repr(v)) for k, v in deb_fields.items()))

    sign_fields.pop('file', None)
    sign_fields = sign_fields.items()
    sign_fields.sort()

    sign = md5(secret + ''.join(k + v for k, v in sign_fields))
    fields['api_sig'] = sign.hexdigest()
    
    resp = post_multipart(HOST, REQUEST_PATH, fields.items(), port=PORT)
    
    try:
        doc = parse(resp)
        if doc.documentElement.tagName != 'rsp':
            raise Exception
    except:
        raise MalformedResponseError('remote host response could not be interpreted')

    logger.debug('Response: %s', doc.toxml())

    # Encapsulate the DOM-madness in an easy to use Tag class.
    rsp = Tag(doc.documentElement)
    
    if rsp.stat == 'fail':
        try:
            err = rsp.get('error')
        except KeyError:
            code = -1
            message = 'unidentified error:\n%s' % doc.toxml().encode('utf8')
        else:
            code = int(err.code)
            message = err.message
            
        raise ResponseError(code, '%s: %s' % (method, message))

    return rsp
            
    
def login(username, password):
    global user
    user = User(send_request('user.login', username=username, password=password))
    return user


def signup(username, password, email, name=None):
    global user
    user = User(send_request('user.signup', username=username, password = password,
                             email=email, name=name))
    return user


def update(docs, **fields):
    owner = None
    for doc in docs:
        assert isinstance(doc, Document)
        doc.__dict__.update(fields)
        if owner is None:
            owner = doc.owner
        elif owner.id != doc.owner.id:
            raise ValueError('all documents must have the same owner')
    send_request('docs.changeSettings',
                 doc_ids=','.join(doc.id for doc in docs),
                 session_key=owner.session_key
                 **fields)


def config(key, secret):
    ns = globals()
    ns['key'] = key
    ns['secret'] = secret


api = User()

logger = logging.getLogger('scribd')
logger.addHandler(NullHandler())
