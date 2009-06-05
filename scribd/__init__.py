'''Scribd client library.

This is a simple yet powerful library for the Scribd API, allowing to write
Python applications or websites that upload, convert, display, search, and
control documents in many formats.

For more information on the Scribd platform, visit:
http://www.scribd.com/about

The underlying API documentation can be found at:
http://www.scribd.com/developers

Copyright (c) 2009 Arkadiusz Wahlig <arkadiusz.wahlig@gmail.com>
'''

__version__ = '0.9.2'


import sys
import httplib
import urllib
import logging
# The md5 module is deprecated since Python 2.5.
if sys.version_info >= (2, 5):
    from hashlib import md5
else:
    from md5 import md5

from multipart import post_multipart
import xmlparse


# Scribd HTTP API host and port.
HOST = 'api.scribd.com'
PORT = 80


# HTTP API request path.
REQUEST_PATH = '/api'


# API key and secret key as given by scribd.com after registering for
# an API account. Set both after importing, either directly or using
# the config() function.
key = ''
secret = ''


class NullHandler(logging.Handler):
    '''Empty logging handler used to prevent a warning if the application
    doesn't use the logging module.
    '''
    def emit(self, record):
        pass


class NotReadyError(Exception):
    '''Exception raised if operation is attempted before the key and secret
    global variables are set.
    '''
    def __init__(self, errstr):
        Exception.__init__(self, str(errstr))


class MalformedResponseError(Exception):
    '''Exception raised if a malformed response is received from the HOST.
    '''
    def __init__(self, errstr):
        Exception.__init__(self, str(errstr))


class ResponseError(Exception):
    '''Exception raised if HOST responses with an error message.
    
    Refer to the API documentation (Error codes section of various methods)
    for explanation of the error codes.
    '''
    def __init__(self, errno, errstr):
        Exception.__init__(self, int(errno), str(errstr))

    def __str__(self):
        return '[Errno %d] %s' % (self[0], self[1])


class Resource(object):
    '''Base class for remote objects that the Scribd API lets to interact
    with. Never used directly, interact with the subclasses instead.
    
    Defines a set of private methods for attributes (fields) management
    and object comparison.
    '''
    # Mapping defining fields extracted from the xml responses.
    # field_name => (field_type, default_value)
    # or
    # field_name => field_type
    # (in which case default value is field_type(''))
    # Default value is used if the field is defined in xml but empty (<field/>).
    # Empty string may not always be the right thing (for example if type is int).
    _fields = {}

    def __init__(self, elem=None):
        '''Instantiates an object of the class. If elem is not None, it
        is a xmlparse.Element object whose subelements are to be converted
        to this object's attributes.
        '''
        self._values = {}
        self._set_fields(elem)

    def _send_request(self, method, **fields):
        '''Sends a request to the HOST and returns the response.
        '''
        return send_request(method, **fields)

    def _iter_fields(self):
        '''Returns a generator iterating over _fields, yielding (name, type,
        default) for each item.
        '''
        for name, cast in self._fields.items():
            if isinstance(cast, tuple):
                cast, default = cast
            else:
                default = cast('')
            yield name, cast, default

    def _set_fields(self, elem=None):
        '''Iterates over _fields and sets the attributes based on the xml
        element. Attributes not defined by the element are deleted.
        '''
        for name, cast, default in self._iter_fields():
            if elem is not None and name in elem:
                value = elem.get(name).value
                if value is not None:
                    default = cast(value)
                setattr(self, name, default)
            elif hasattr(self, name):
                delattr(self, name)
        self._changed_fields()

    def _changed_fields(self):
        '''Compares the current attributes with the ones stored in
        self._values and returns a mapping of the ones that differ.
        Stores the current values in self._values afterwards.
        '''
        fields = {}
        for name, cast, default in self._iter_fields():
            value = getattr(self, name, default)
            if value != self._values.get(name, default):
                fields[name] = value
        if fields:
            self._values = {}
            for name, cast, default in self._iter_fields():
                self._values[name] = getattr(self, name, default)
        return fields

    def __repr__(self):
        return '<%s.%s %s at 0x%x>' % (self.__class__.__module__,
            self.__class__.__name__, repr(self.id), id(self))

    def __eq__(self, other):
        if isinstance(other, Resource):
            return (self.id == other.id)
        return object.__eq__(self, other)

    def _get_id(self):
        # Overridden in subclasses. Note that the id property has to
        # be redefined there too.
        return ''

    id = property(_get_id)


class User(Resource):
    '''Represents a Scribd user.

    Don't instantiate directly, use login() or signup() functions instead.
    '''
    _fields = {'session_key': str,
               'user_id': str,
               'username': str,
               'name': unicode}

    def _send_request(self, method, **fields):
        '''Sends a request to the HOST and returns the response.
        '''
        # Add the session key to the call but only if this isn't the
        # default (API account) user.
        if hasattr(self, 'session_key'):
            fields['session_key'] = self.session_key
        return Resource._send_request(self, method, **fields)

    def all(self, **kwargs):
        '''Returns a list of all user documents.
        '''
        elem = self._send_request('docs.getList', **kwargs)
        return [Document(result, self) for result in elem.get('resultset')]

    def xall(self, **kwargs):
        '''Returns a generator object iterating over all user documents
        and creating Document objects on demand.
        '''
        while True:
            elem = self._send_request('docs.getList', **kwargs)
            results = elem.get('resultset')
            if len(results) == 0:
                break
            for result in results:
                yield Document(result, self)
            if len(results) < kwargs.get('limit', 0):
                break
            kwargs['offset'] = kwargs.get('offset', 0) + len(results)

    def get(self, doc_id):
        '''Returns a document with the specified id.
        '''
        elem = self._send_request('docs.getSettings', doc_id=doc_id)
        return Document(elem, self)

    def find(self, query, **kwargs):
        '''Searches for documents and returns a list of them.
        
        Refer to the API documentation (docs.search method) for
        possible parameters. You may use limit and offset parameters
        instead of num_results and num_start. Note that initial
        num_start value is 1 whereas offset is 0.
        
        Note that only for scope='user' (which is the default), the
        returned documents will have the owner attribute set to this
        user object. Otherwise the user cannot be determined so the
        owner attribute will be None. You can set it later if you
        want.
        '''
        if 'limit' in kwargs:
            kwargs['num_results'] = kwargs['limit']
        if 'offset' in kwargs:
            kwargs['num_start'] = kwargs['offset'] + 1
        elem = self._send_request('docs.search', query=query, **kwargs)
        owner = None
        if kwargs.get('scope', 'user') == 'user':
            owner = self
        return [Document(result, owner) for result in elem.get('result_set')]

    def xfind(self, query, **kwargs):
        '''Returns a generator object searching for documents and iterating
        over them.
        
        Always iterates over all found documents. Takes the same arguments
        as find() with the exception of limit/num_results which tells how
        many results will be acquired from a single API call. If all matches
        from a single call are processed, the call is repeated for the next
        chunk od results. The happens until all found documents are processed.
        If you're not interested in all results, stop the iterator earlier.
        '''
        if 'limit' in kwargs:
            kwargs['num_results'] = kwargs['limit']
        if 'offset' in kwargs:
            kwargs['num_start'] = kwargs['offset'] + 1
        owner = None
        if kwargs.get('scope', 'user') == 'user':
            owner = self
        while True:
            elem = self._send_request('docs.search', query=query, **kwargs)
            results = elem.get('result_set')
            for result in results:
                yield Document(result, owner)
            kwargs['num_start'] = int(results.firstResultPosition) + \
                                   int(results.totalResultsReturned)
            if kwargs['num_start'] >= int(results.totalResultsAvailable):
                break

    def upload(self, file, **kwargs):
        '''Uploads a new document and returns a document object.
        
        file is either a file-alike object providing read() method and name
        attribute or a string defining the document's URL.
        '''
        if isinstance(file, str):
            elem = self._send_request('docs.uploadFromUrl', url=file, **kwargs)
        else:
            elem = self._send_request('docs.upload', file=file, **kwargs)
        doc = Document(elem, self)
        doc.load()
        return doc

    def get_autologin_url(self, next_url, **kwargs):
        '''Creates and returns an URL that logs the user in when visited and
        redirects to the specified URL.
        
        The specified URL must point to scribd.com domain.
        '''
        elem = self._send_request('user.getAutoSigninUrl', next_url=next_url,
                                  **kwargs)
        return str(elem.get('url').value)

    def _get_id(self):
        return getattr(self, 'user_id', 'default')

    id = property(_get_id)


class CustomUser(User):
    '''Provides an easy way to implement virtual users within a single Scribd
    user account.
    
    Just instantiate this class passing a virtual user name to the constructor.
    The resulting object provides all methods of the standard user object but
    operating on a subset of the Scribd API account documents, associated with
    the specified virtual username.
    '''
    _fields = {}
    
    def __init__(self, my_user_id):
        User.__init__(self)
        self.my_user_id = my_user_id
        
    def _send_request(self, method, **fields):
        '''Sends a request to the HOST and returns the response.
        '''
        fields['my_user_id'] = self.my_user_id
        return User._send_request(self, method, **fields)

    def get_autologin_url(self, next_url, **kwargs):
        '''This method is not supported by custom users.
        '''
        raise NotImplementedError('autologin not supported by custom users')

    def _get_id(self):
        return self.my_user_id

    id = property(_get_id)


class Document(Resource):
    '''Represents a Scribd document.
    
    Don't instantiate directly, use methods of the user objects instead.
    
    Objects have a owner attribute pointing to the owning user object.
    The owner may be unknown in which case the it is None and may be set
    by you if you know the user.
    
    Document objects provide a number of attributes representing the
    document properties. Refer to the API documentation (Result explanation
    section of the docs.getList method) for their names and meaning.
    
    If the document belongs to the current APi account or the owner
    is a valid logged in user, the load() method can be used to load
    extended properties. Refer to the API documentation (Result
    explanation section of the docs.getSettings method) for their names
    and meaning.
    '''
    _fields = {'doc_id': str,
               'title': unicode,
               'description': unicode,
               'tags': unicode,
               'license': str,
               'thumbnail_url' : str,
               'page_count': (int, 0),
               # These fields are valid for owned docs only:
               'access_key': str,
               'secret_password': str,
               'conversion_status': str,
               'access': str,
               'show_ads': str,
               'author': unicode,
               'publisher': unicode,
               'when_published': str,
               'edition': unicode}

    def __init__(self, elem, owner):
        Resource.__init__(self, elem)
        self.owner = owner

    def _send_request(self, method, **fields):
        '''Sends a request to the HOST and returns the response.
        '''
        if self.owner is not None:
            return self.owner._send_request(method, **fields)
        return Resource._send_request(self, method, **fields)

    def get_conversion_status(self):
        '''Obtains and returns the document conversion status.
        Refer to the API documentation for values explanation.
        '''
        elem = self._send_request('docs.getConversionStatus', doc_id=self.doc_id)
        return str(elem.get('conversion_status').value)

    def delete(self):
        '''Deletes the document from Scribd service.
        '''
        self._send_request('docs.delete', doc_id=self.doc_id)

    def get_download_url(self, format='original'):
        '''Returns an URL pointing to the document file.
        The argument specifies the file format. Refer to the API documentation
        for possible values.
        '''
        elem = self._send_request('docs.getDownloadUrl', doc_id=self.doc_id,
                                  doc_type=format)
        return str(elem.get('download_link').value)

    def load(self):
        '''If the document belongs to the owner set of if there is no owner
        and it belongs to the current API account, this method populates
        the extended attributes of the document with their values. Otherwise
        a ResponseError is raised with insufficient privileges message.
        '''
        elem = self._send_request('docs.getSettings', doc_id=self.doc_id)
        self._set_fields(elem)

    def save(self):
        '''Saves the changed attributes.
        This can be done only if the document owner has sufficent priviledges.
        '''
        fields = self._changed_fields()
        if fields:
            self._send_request('docs.changeSettings', doc_ids=self.doc_id,
                               **fields)
            return True
        return False

    def _get_id(self):
        return self.doc_id

    id = property(_get_id)


def send_request(method, **fields):
    '''Sends an API request to the HOST. method is the name of the method
    to perform. Any keyword arguments will be passed as arguments to the
    method.
    
    If a keyword argument's value is None, the argument is ignored.
    
    Returns an xmlparse.Element object representing the root of the HOST's
    xml resposne.
    
    Raises a MalformedResponseError if the xml response cannot be parsed
    or the root element isn't 'rsp'.
    
    Raises a ResponseError if the response indicates an error. The exception
    object contains the error code and message reported by the HOST.
    '''
    if not key or not secret:
        raise NotReadyError('configure api key and secret key first')
    if not method:
        raise ValueError('method must be specified')

    fields['method'] = method
    fields['api_key'] = key

    sign_fields = {}
    for k, v in fields.items():
        if v is not None:
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
        elem = xmlparse.parse(resp)
        if elem.name != 'rsp':
            raise Exception
    except:
        raise MalformedResponseError('remote host response could not be interpreted')

    logger.debug('Response: %s', elem.toxml())

    if elem.stat == 'fail':
        try:
            err = elem.get('error')
        except KeyError:
            code = -1
            message = 'unidentified error:\n%s' % \
                      elem.toxml().encode('ascii', 'replace')
        else:
            code = int(err.code)
            message = err.message

        raise ResponseError(code, '%s: %s' % (method, message))

    return elem


def login(username, password):
    '''Logs the given Scribd user in and returns the corresponding user object.
    '''
    return User(send_request('user.login', username=username, password=password))


def signup(username, password, email, name=None):
    '''Creates a new Scribd user and returns the corresponding user object.
    The user is already logged in.
    '''
    return User(send_request('user.signup', username=username, password = password,
                             email=email, name=name))


def update(docs, **fields):
    '''A faster way to set the same attribute of many documents. Instead of:

        for doc in docs:
            doc.some_attribute = some_value
            doc.save()
    use:

        update(docs, some_sttribute=some_value)
        
    All documents must have the same owner. The operation requires only one
    API call.
    '''
    owner = None
    for doc in docs:
        if not isinstance(doc, Document):
            raise ValueError('expected a sequence of Document objects')
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
    '''Sets the scribd.key and scribd.secret values in one call.
    
    The values have to be set to the strings given by scribd.com
    after registering for an API account.
    
    This function has to be called before any operations involving
    API calls are performed.
    '''
    ns = globals()
    ns['key'] = key
    ns['secret'] = secret


# The default API account user. Note that it doesn't support standard
# user attributes like username or id.
user = User()


# Create a scribd logger. If logging is enabled by the application, scribd
# will log all performed API calls.
logger = logging.getLogger('scribd')
logger.addHandler(NullHandler())
