"""
Scribd client library.

This is a simple yet powerful library for the Scribd API, allowing to write
Python applications or websites that upload, convert, display, search, and
control documents in many formats using the Scribd platform.

For more information on the Scribd platform, visit:
http://www.scribd.com/about

The underlying RESTful API documentation can be found at:
http://www.scribd.com/developers

Copyright (c) 2009, Arkadiusz Wahlig <arkadiusz.wahlig@gmail.com>

Distributed under the new BSD License, see the
accompanying LICENSE file for more information.
"""

__version__ = '1.0.0'

__all__ = ['NotReadyError', 'MalformedResponseError', 'ResponseError',
           'Resource', 'User', 'VirtualUser', 'Document', 'login',
           'signup', 'update', 'find', 'xfind', 'config', 'api_user']
           

#
# Imports
#

import sys
import logging
import os
from time import time

# Both md5 module (deprecated since Python 2.5) and hashlib provide the
# same md5 object.
if sys.version_info >= (2, 5):
    from hashlib import md5
else:
    from md5 import md5

from scribd.multipart import post_multipart
from scribd import xmlparse


#
# Constants
#

# Scribd HTTP API host and port.
HOST = 'api.scribd.com'
PORT = 80

# Scribd HTTP API request path.
REQUEST_PATH = '/api'

# API key and secret as given by Scribd after registering for an API account.
# Set both after importing, either directly or using the config() function.
api_key = ''
api_secret = ''


#
# Exceptions
#

class Error(Exception):
    """Base class for all exceptions in this package."""
    
    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)
    

class NotReadyError(Error):
    """Exception raised if operation is attempted before the API key and
    secret are set.
    """
    
    def __init__(self, errstr='error'):
        Exception.__init__(self, str(errstr))


class MalformedResponseError(Error):
    """Exception raised if a malformed response is received from the HOST."""
    
    def __init__(self, errstr='error'):
        Exception.__init__(self, str(errstr))


class ResponseError(Error):
    """Exception raised if HOST responses with an error message.
       
    Refer to the API documentation (Error codes section of various methods)
    for explanation of the error codes.
    """
    
    def __init__(self, errno=-1, errstr='error'):
        Exception.__init__(self, int(errno), str(errstr))

    def __str__(self):
        return '[Errno %d] %s' % (self[0], self[1])


#
# Classes
#

class NullHandler(logging.Handler):
    """Empty logging handler used to prevent a warning if the application
    doesn't use the logging module.
    """
    
    def emit(self, record):
        pass


class Resource(object):
    """Base class for remote objects that the Scribd API allows
    to interact with.
    
    This class is never instantiated, only subclassed.
    
    Every object features a set of resource attributes that are
    stored and managed by the Scribd platform. They are accessed
    and used like any other Python object attributes but are
    stored in a separate container.
    """

    def __init__(self, xml=None):
        # Instantiates an object of the class.
        #
        # If "xml" is not None, it is a xmlparse.Element object whose
        # subelements are to be converted to this object's resource
        # attributes.

        self._attributes = {} # Attributes as loaded from the XML.
        self._set_attributes = {} # Attributes set externally.

        # Create a list of instance variables. All variables used by
        # the object during its lifetime have to be setup at this point.
        # This is used to distinguish between instance variables and
        # the resource attributes.
        self._instance_vars_names = self.__dict__.keys()

        if xml is not None:
            self._load_attributes(xml)
            
    def get_attributes(self):
        """Returns a dictionary with the resource attributes."""
        attrs = self._attributes.copy()
        attrs.update(self._set_attributes)
        return attrs
        
    def _send_request(self, method, **fields):
        """Sends a request to the HOST and returns the XML response."""
        return send_request(method, **fields)
        
    def _load_attributes(self, xml):
        """Adds resource attributes to this object based on XML
        response from the HOST.
        """
        for element in xml:
            text = element.text
            if text is not None:
                try:
                    type = element.attrs.get('type', None)
                    if type == 'integer':
                        text = int(text)
                    elif type == 'float':
                        text = float(text)
                    else:
                        text = str(text)
                except (UnicodeError, ValueError):
                    pass
            self._attributes[element.name] = text
            self._set_attributes.pop(element.name, None)
            
    def __getattr__(self, name):
        # The attribute is treated as a resource attribute if
        # self._instance_vars_names is defined and it doesn't
        # contain the attribute name.
        if name not in self.__dict__.get('_instance_vars_names', (name,)):
            if name == 'id':
                return self._get_id()
            try:
                return self._set_attributes[name]
            except KeyError:
                pass
            try:
                return self._attributes[name]
            except KeyError:
                pass
        raise AttributeError('%s object has no attribute %s' % \
                             (repr(self.__class__.__name__), repr(name)))
            
    def __setattr__(self, name, value):
        # The attribute is treated as a resource attribute if
        # self._instance_vars_names is defined and it doesn't
        # contain the attribute name.
        if name in self.__dict__.get('_instance_vars_names', (name,)):
            object.__setattr__(self, name, value)         
        else:
            self._set_attributes[name] = value

    def __repr__(self):
        return '<%s.%s %s at 0x%x>' % (self.__class__.__module__,
            self.__class__.__name__, repr(self.id), id(self))

    def __eq__(self, other):
        if isinstance(other, Resource):
            return (self.id == other.id)
        return object.__eq__(self, other)
        
    def __hash__(self):
        return hash(self.id)

    def _get_id(self):
        # Overridden in subclasses.
        return ''


class User(Resource):
    """Represents a Scribd user.

    Use login() or signup() functions to instantiate.

    Resource attributes:
        Refer to "Result explanation" section of:
        http://www.scribd.com/developers/api?method_name=user.login
    """
    
    def _send_request(self, method, **fields):
        """Sends a request to the HOST and returns the XML response."""
        # Add the session key to the call. If this is the default
        # (API account) user, add None (which will be ignored).
        fields['session_key'] = getattr(self, 'session_key', None)
        return Resource._send_request(self, method, **fields)

    def all(self, **kwargs):
        """Returns a list of all user documents.

        Parameters:
            Refer to the "Parameters" section of:
            http://www.scribd.com/developers/api?method_name=docs.getList
          
            Parameters "api_key", "api_sig", "session_key", "my_user_id"
            are managed internally by the library.
          
        Returns:
            A list of [Document] objects.

            Refer to "Result explanation" section of:
            http://www.scribd.com/developers/api?method_name=docs.getList
            for a list of document's initial resource attributes.
        """
        xml = self._send_request('docs.getList', **kwargs)
        return [Document(result, self) for result in xml.get('resultset')]

    def xall(self, **kwargs):
        """Similar to all() method but returns a generator object
        iterating over all user documents.

        Parameters:
            Refer to the "Parameters" section of:
            http://www.scribd.com/developers/api?method_name=docs.getList

            Parameters "api_key", "api_sig", "session_key", "my_user_id"
            are managed internally by the library.

            Parameter "limit" is not supported.
          
        Additional parameters:
          page_size
            (optional) The number of documents acquired by a single API
            call. The generator repeats the calls until all documents are
            returned. Defaults to 100.

        Returns:
            A generator object yielding [Document] objects.

            Refer to "Result explanation" section of:
            http://www.scribd.com/developers/api?method_name=docs.getList
            for a list of document's initial resource attributes.

        Note. If you're not interested in all documents (currently there
        may be max. 1000 of them), just stop iterating the generator object.
        """
        kwargs['limit'] = kwargs.pop('page_size', 100)
        while True:
            xml = self._send_request('docs.getList', **kwargs)
            results = xml.get('resultset')
            for result in results:
                yield Document(result, self)
            if len(results) < kwargs['limit']:
                break
            kwargs['offset'] = kwargs.get('offset', 0) + len(results)

    def get(self, doc_id):
        """Returns a document with the specified id.
        
        Parameters:
          doc_id
            (required) Identifier of the document to be returned.
            The user has to be the owner of this document.

        Returns:
            A [Document] object.

            Refer to "Result explanation" section of:
            http://www.scribd.com/developers/api?method_name=docs.getSettings
            for a list of document's initial resource attributes.
        """
        xml = self._send_request('docs.getSettings', doc_id=doc_id)
        return Document(xml, self)

    def find(self, query, **kwargs):
        """Searches for documents and returns a list of them.
        
        Parameters:
            Refer to the "Parameters" section of:
            http://www.scribd.com/developers/api?method_name=docs.search
          
            Parameters "api_key", "api_sig", "session_key", "my_user_id"
            are managed internally by the library.

            Parameter "num_start" is not supported.
            Parameter "num_results" is not supported.
          
        Additional parameters:
          offset
            (optional) The offset into the list of documents.
          limit
            (optional) The number of documents to return
            (default 10, max 1000).

        Note on the "scope" parameter:
            Only if scope=='user', the returned documents will have the
            owner attribute set to this user object. Otherwise it will be
            the scribd.api_user which will impact the ability to change
            the document's properties. You may set the owner attributes
            later if you have can determine the documents owner yourself.
            Refer to the [Document] class for operations requiring a proper
            owner object.

        Returns:
            A list of [Document] objects.

            Refer to "Result explanation" section of:
            http://www.scribd.com/developers/api?method_name=docs.search
            for a list of document's initial resource attributes.
        """
        kwargs['num_results'] = kwargs.pop('limit', None)
        kwargs['num_start'] = kwargs.pop('offset', 0) + 1
        xml = self._send_request('docs.search', query=query, **kwargs)
        owner = api_user
        if kwargs.get('scope', 'user') == 'user':
            owner = self
        return [Document(result, owner) for result in xml.get('result_set')]

    def xfind(self, query, **kwargs):
        """Similar to find() method but returns a generator object searching
        for documents and iterating over them.
        
        Parameters:
            Refer to the "Parameters" section of:
            http://www.scribd.com/developers/api?method_name=docs.search
          
            Parameters "api_key", "api_sig", "session_key", "my_user_id"
            are managed internally by the library.

            Parameter "num_start" is not supported.
            Parameter "num_results" is not supported.
          
        Additional parameters:
          offset
            (optional) The offset into the list of documents.
          page_size
            (optional) The number of documents acquired by a single API
            call. The calls are repeated until all documents are returned.

        Returns:
            A generator object yielding [Document] objects.

            Refer to "Result explanation" section of:
            http://www.scribd.com/developers/api?method_name=docs.search
            for a list of document's initial resource attributes.

        Note. If you're not interested in all documents (currently there
        may be max. 1000 of them), just stop iterating the generator object.
        """
        kwargs['num_results'] = kwargs.get('page_size', None) 
        kwargs['num_start'] = kwargs.get('offset', 0) + 1
        owner = api_user
        if kwargs.get('scope', 'user') == 'user':
            owner = self
        while True:
            xml = self._send_request('docs.search', query=query, **kwargs)
            results = xml.get('result_set')
            for result in results:
                yield Document(result, owner)
            kwargs['num_start'] = int(results.attrs['firstResultPosition']) + \
                                  int(results.attrs['totalResultsReturned']) - 1
            if kwargs['num_start'] >= int(results.attrs['totalResultsAvailable']):
                break

    def upload(self, file, name=None, **kwargs):
        """Uploads a file object as a new document and returns the
        corresponding document object.
        
        Parameters:
            Refer to the "Parameters" section of:
            http://www.scribd.com/developers/api?method_name=docs.upload

            Parameters "api_key", "api_sig", "session_key", "my_user_id"
            are managed internally by the library.

            Parameter "file" is documented below.

          file
            (required) File-alike object to upload. The file is loaded
            into memory using the read() method and uploaded.
          name
            (optional) Name of the file. Either a full path or just the
            name. Only the name is used. Does not have to point to an
            existing file. If None, the name will be read from the "name"
            attribute of the file object (objects created using the open()
            built-in function provide this attribute).

        Returns:
            A [Document] object.

            Refer to "Result explanation" section of:
            http://www.scribd.com/developers/api?method_name=docs.upload
            for a list of document's initial resource attributes.
        """
        if name is None:
            name = file.name
        name = os.path.basename(name)
        if 'doc_type' not in kwargs:
            kwargs['doc_type'] = os.path.splitext(name)[-1]
        kwargs['doc_type'] = kwargs['doc_type'].lstrip('.').lower()
        xml = self._send_request('docs.upload', file=(file.read(), name), **kwargs)
        return Document(xml, self)
        
    def upload_from_url(self, url, **kwargs):
        """Uploads a file from a remote URL as a new document and returns
        the corresponding document object.
        
        Parameters:
            Refer to the "Parameters" section of:
            http://www.scribd.com/developers/api?method_name=docs.upload

            Parameters "api_key", "api_sig", "session_key", "my_user_id"
            are managed internally by the library.
            
            Parameter "file" is not supported.

          url
            (required) A URL of the document to upload.

        Returns:
            A [Document] object.

            Refer to "Result explanation" section of:
            http://www.scribd.com/developers/api?method_name=docs.upload
            for a list of document's initial resource attributes.
        """
        if 'doc_type' not in kwargs:
            kwargs['doc_type'] = os.path.splitext(url)[-1]
        kwargs['doc_type'] = kwargs['doc_type'].lstrip('.').lower()
        xml = self._send_request('docs.uploadFromUrl', url=url, **kwargs)
        return Document(xml, self)

    def get_autologin_url(self, next_url=''):
        """Creates and returns an URL that logs the user in when visited and
        redirects to the specified URL.
        
        Parameters:
            Refer to the "Parameters" section of:
            http://www.scribd.com/developers/api?method_name=user.getAutoSigninUrl

            Parameters "api_key", "api_sig", "session_key", "my_user_id"
            are managed internally by the library.

        Returns:
            An URL (string).
        """
        xml = self._send_request('user.getAutoSigninUrl', next_url=next_url)
        return str(xml.get('url').text)

    def _get_id(self):
        return getattr(self, 'user_id', 'api_user')


class VirtualUser(User):
    """Provides an easy way to implement virtual users within the current
    Scribd API account.
    
    This is useful if Scribd is used as a backend for a platform with its
    own user authentication system.
    
    Virtual users are created just by instantiating this class passing the
    name of the virtual user to the constructor. This will most probably
    be the name used by your own authentication system.

    Because this is a subclass of the [User] class, the virtual users provide
    the same set of operations (except get_autologin_url()) as normal users.
    
    Resource attributes:
      None.
    """
    
    def __init__(self, my_user_id):
        """Instantiates a new object.
        
        Parameters:
          my_user_id
            Name of the virtual user. Every time an object is created
            with the same name, it will refer to the same virtual user.
        """
        self.my_user_id = my_user_id
        User.__init__(self)
        
    def _send_request(self, method, **fields):
        """Sends a request to the HOST and returns the XML response."""
        fields['my_user_id'] = self.my_user_id
        return User._send_request(self, method, **fields)

    def get_autologin_url(self, next_path=''):
        """This method is not supported by virtual users."""
        raise NotImplementedError('autologin not supported by virtual users')

    def _get_id(self):
        return self.my_user_id


class Document(Resource):
    """Represents a Scribd document.
    
    Use methods of the [User] objects to instantiate.
    
    Attributes:
      owner
        A [User] object owning the document. This always is a valid
        object but may not be the true owner of the document if it could
        not be determined. This may be the case if the document was obtained
        from find() or xfind() function/method. In the worst case, the owner
        will be set to the scribd.api_user object which is the default user
        associated with the current API account.
        
        You may set this attribute if you can determine the true owner
        yourself.
        
        Refer to the object methods documentation to learn which ones
        require a true owner to be set.
    
    Resource attributes:
        The initial set of the attributes depend on how this object
        was obtained.

        Refer to "Result explanation" section of:
        http://www.scribd.com/developers/api?method_name=docs.getList
        if the object was obtained by the [User] object's all() or
        xall() methods.
      
        Refer to "Result explanation" section of:
        http://www.scribd.com/developers/api?method_name=docs.search
        if the object was obtained by find() or xfind() (either global
        functions or [User] object's methods).
      
        Refer to "Result explanation" section of:
        http://www.scribd.com/developers/api?method_name=docs.upload
        if the object was obtained by one of the [User] object's
        uploads methods.

        Refer to "Result explanation" section of:
        http://www.scribd.com/developers/api?method_name=docs.getSettings
        if the object was obtained by the [User] object's get() method.

        If the owner attribute points to a true owner of the document,
        the load() method may be used to obtain a full set of resource
        attributes. For more information refer to the load() method
        documentation.
    """
    
    def __init__(self, xml, owner):
        self.owner = owner
        Resource.__init__(self, xml)

    def _send_request(self, method, **fields):
        """Sends a request to the HOST and returns the XML response."""
        return self.owner._send_request(method, **fields)

    def get_conversion_status(self):
        """Obtains and returns the document current conversion status.
        
        Returns:
            A string. Refer to the "Result explanation" section of:
            http://www.scribd.com/developers/api?method_name=docs.getConversionStatus

        Requires the document owner to be the user that uploaded this
        document.
        """
        xml = self._send_request('docs.getConversionStatus', doc_id=self.doc_id)
        return str(xml.get('conversion_status').text)

    def delete(self):
        """Deletes the document from Scribd platform.

        Requires the document owner to be the user that uploaded this
        document.
        """
        self._send_request('docs.delete', doc_id=self.doc_id)

    def get_download_url(self, doc_type='original'):
        """Returns a link that can be used to download a static version of the
        document.
        
        Parameters:
            Refer to the "Parameters" section of:
            http://www.scribd.com/developers/api?method_name=docs.getDownloadUrl

            Parameters "api_key", "api_sig", "session_key", "my_user_id",
            "doc_id" are managed internally by the library.
          
        Returns:
            An URL (string).
        """
        xml = self._send_request('docs.getDownloadUrl', doc_id=self.doc_id,
                                 doc_type=doc_type)
        return str(xml.get('download_link').text)

    def load(self):
        """Retrieves the detailed meta-data for this document and updates
        object's resource attributes.
        
        Refer to the "Result explanation" section of:
        http://www.scribd.com/developers/api?method_name=docs.getSettings
        for the names and descriptions of the resource attributes.
        
        Requires the document owner to be the user that uploaded this
        document.
        """
        xml = self._send_request('docs.getSettings', doc_id=self.doc_id)
        self._load_attributes(xml)

    def save(self):
        """Saves the changed object's resource attributes.

        Has to be called after a resource attribute has been altered
        to make the change permanent.

        Refer to the "Parameters" section of:
        http://www.scribd.com/developers/api?method_name=docs.changeSettings
        for the names and descriptions of the resource attributes
        that are saved by this call.

        Requires the document owner to be the user that uploaded this
        document.
        """
        if self._set_attributes:
            self._send_request('docs.changeSettings', doc_ids=self.doc_id,
                               **self._set_attributes)
            self._attributes.update(self._set_attributes)
            self._set_attributes.clear()
            return True
        return False
        
    def replace(self, file, name=None, **kwargs):
        """Uploads a new file in place of the current document. All
        resource attributes including doc_id remain intact.
        
        Parameters:
            Refer to the [User].upload() method.
          
            Parameter "rev_id" is managed internally by the library.

        Requires the document owner to be the user that uploaded this
        document.
        """
        doc = self.owner.upload(file, name, rev_id=self.doc_id, **kwargs)
        self._attributes.update(doc._attributes)

    def replace_from_url(self, url, **kwargs):
        """Uploads a new file from a remote URL in place of the current
        document. All resource attributes including doc_id remain intact.
        
        Parameters:
            Refer to the [User].upload_from_url() method.

            Parameter "rev_id" is managed internally by the library.

        Requires the document owner to be the user that uploaded this
        document.
        """
        doc = self.owner.upload_from_url(url, rev_id=self.doc_id, **kwargs)
        self._attributes.update(doc._attributes)

    def get_scribd_url(self):
        """Returns a link to the document's page on scribd.com.
        
        Works for private documents too by adding the secret
        password to the link. May call the load() method to
        obtain the secret password.
        """
        try:
            chars = []
            for c in self.title.encode('ascii', 'replace'):
                if not c.isalnum():
                    c = ' '
                chars.append(str(c))
            title = '-'.join(''.join(chars).split())
        except AttributeError:
            title = ''
        try:
            if not hasattr(self, 'access'):
                self.load()
        except Error:
            pass
        else:
            if self.access == 'private':
                title += '?secret_password=' + self.secret_password
        return 'http://www.scribd.com/doc/%s/%s' % (self.doc_id, title)

    def _get_id(self):
        return self.doc_id


#
# Functions
#

def send_request(method, **fields):
    """Sends an API request to the HOST and returns the XML response.
    
    Parameters:
      method
        Name of the method to perform.
      keyword arguments
        Sent as method arguments. If a keyword argument's value is None,
        the argument is ignored (not sent).
    
    Returns:
        An xmlparse.Element object representing the root of the HOST's
        XML response.
    
    Raises:
      MalformedResponseError
        If the XML response cannot be parsed or the root element isn't 'rsp'.
      ResponseError
        If the response indicates an error. The exception object contains
        the error code and message reported by the HOST.
    """
    if not api_key or not api_secret:
        raise NotReadyError('configure API key and secret first')
    if not method:
        raise ValueError('method must be specified')

    fields['method'] = method
    fields['api_key'] = api_key

    for k, v in fields.items():
        if v is None:
            del fields[k]
        else:
            if isinstance(v, unicode):
                v = v.encode('utf8')
            elif isinstance(v, tuple):
                v = (v[0], str(v[1]))
            else:
                v = str(v)
            fields[k] = v

    deb_fields = fields.copy()
    del deb_fields['method'], deb_fields['api_key']
    t = deb_fields.get('file', None)
    if t is not None:
        deb_fields['file'] = (t[0][:16] + '(...)', t[1])
    logger.debug('Request: %s(%s)', method,
                 ', '.join('%s=%s' % (k, repr(v)) for k, v in deb_fields.items()))

    sign_fields = fields.copy()
    sign_fields.pop('file', None)
    sign_items = sign_fields.items()
    sign_items.sort()
    sign = md5(api_secret + ''.join(k + v for k, v in sign_items))
    fields['api_sig'] = sign.hexdigest()

    headers = {'Cache-Control': 'no-store'}

    start_time = time()
    while True:
        try:
            resp = post_multipart(HOST, REQUEST_PATH, fields.items(), headers, PORT)
        except Exception, err:
            if time() - start_time < 10:
                continue
            raise NotReadyError(str(err))
        
        status = resp.getheader('Status', '200').split()[0]
        if status == '200':
            # Content-Type must be application/xml.
            ctype = resp.getheader('Content-Type', 'text/plain').split(';')[0]
            if ctype == 'application/xml':
                try:
                    xml = xmlparse.parse(resp)
                    if xml.name != 'rsp':
                        raise Exception
                except:
                    raise MalformedResponseError(
                            'remote host response could not be interpreted')
            else:
                raise MalformedResponseError(
                        'unexpected remote host response format: %s' % ctype)
        elif status == '500': # Internal Server Error
            # Retrying usually helps if this happens so lets do so for max. 10 seconds.
            if time() - start_time < 10:
                continue
            raise NotReadyError('remote host internal error')
        else:
            raise NotReadyError('remote host status error: %s' % status)
        break

    logger.debug('Response: %s', xml.toxml())

    if xml.attrs['stat'] == 'fail':
        try:
            err = xml.get('error')
        except KeyError:
            code = -1
            message = 'unidentified error:\n%s' % \
                      xml.toxml().encode('ascii', 'replace')
        else:
            code = int(err.attrs['code'])
            message = err.attrs['message']

        raise ResponseError(code, '%s: %s' % (method, message))

    return xml


def login(username, password):
    """Logs the given Scribd user in and returns the corresponding [User] object.
    
    Parameters:
      username
        Name of the user.
      password
        The user's password.

    Returns:
        A [User] object.
    """
    return User(send_request('user.login', username=username, password=password))


def signup(username, password, email, name=None):
    """Creates a new Scribd user and returns the corresponding [User] object.
    The user is already logged in.
    
    Parameters:
      username
        Name of the new user.
      password
        Password of the new user.
      email
        E-mail address of the user.

    Returns:
        A [User] object.
    """
    return User(send_request('user.signup', username=username, password = password,
                             email=email, name=name))


def update(docs, **fields):
    """A faster way to set the same attribute of many documents.
    
    Parameters:
      docs
        A sequence of [Document] objects.
      keyword arguments
        Document attributes to set.
    
    Example:
        Instead of:

            for doc in docs:
                doc.some_attribute_1 = some_value_1
                doc.some_attribute_2 = some_value_2
                doc.save()
        use:

            update(docs, some_attribute_1=some_value_1,
                         some_attribute_2=some_value_2)
        
    All documents must have the same owner. The operation is faster because
    it requires only one API call.
    """
    owner = None
    for doc in docs:
        if not isinstance(doc, Document):
            raise ValueError('expected a sequence of Document objects')
        if owner is None:
            owner = doc.owner
        elif owner != doc.owner:
            raise ValueError('all documents must have the same owner')
    if owner is not None:
        owner._send_request('docs.changeSettings',
                            doc_ids=','.join(doc.id for doc in docs),
                            **fields)
    # We have to set the attributes one by one to let the document's
    # __setattr__() decide what to do with it.
    for doc in docs:
        for name, value in fields.items():
            setattr(doc, name, value)


def find(query, **kwargs):
    """Searches for public documents and returns a list of them.

    Parameters:
        Refer to [User].find() method.
      
    Returns:
        A list of [Document] objects.

    This function searches for public documents by default.
    
    The returned document have the owner attribute set to the
    scribd.api_user object.
    """
    if 'scope' not in kwargs:
        kwargs['scope'] = 'all'
    return api_user.find(query, **kwargs)


def xfind(query, **kwargs):
    """Similar to find() function but returns a generator object
    searching for documents and iterating over them.
    
    Parameters:
        Refer to [User].xfind() method.
      
    Returns:
        A generator object yielding [Document] objects.

    This function searches for public documents by default.
    
    The returned document have the owner attribute set to the
    scribd.api_user object.
    """
    if 'scope' not in kwargs:
        kwargs['scope'] = 'all'
    return api_user.xfind(query, **kwargs)


def config(key, secret):
    """Configures the API key and secret. These values have to be
    configured before any operation involving API calls can be performed.
    
    Parameters:
      key
        The API key assigned to your Scribd user account.
      secret
        The API secret assigned to your Scribd user account.
    
    API key and secret values are obtained by signing up for a Scribd
    account and registering it as an API account. The website will in
    turn provide you with both values.
    """
    global api_key, api_secret
    api_key = key
    api_secret = secret


#
# Objects
#

# The API account user. Represents the user that registered the current
# API account. Note that the object doesn't support standard user
# object attributes like "name" or "username". These are supported only
# by properly logged in users (see the login() function) and may be
# accessed for this user in the same way (by logging in).
api_user = User()

# Create a scribd logger using the logging library. If logging is enabled
# by the application, scribd library will log all performed API calls.
logger = logging.getLogger('scribd')
logger.addHandler(NullHandler())
