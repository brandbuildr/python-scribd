#!/usr/bin/env python
'''
Scribd client library distutils setup script.

Copyright (c) 2009, Arkadiusz Wahlig <arkadiusz.wahlig@gmail.com>

Distributed under the BSD License, see the
accompanying LICENSE file for more information.
'''

import sys
import os
import pydoc
import inspect
from distutils.core import setup
from distutils.cmd import Command


# Import scribd distribution package.
import scribd


class WikiDoc(pydoc.TextDoc):
    def document(self, object, name=None, *args):
        # Monkey-patch some pydoc functions.
        _visiblename = pydoc.visiblename
        def visiblename(name, all=None):
            # Hide all private and special names
            # in an effort to make the doc more readable.
            if name.startswith('_'):
                return 0
            return _visiblename(name, all)
        pydoc.visiblename = visiblename
        _classname = pydoc.classname
        def classname(object, modname):
            name = _classname(object, modname)
            # Name lookup falls back to built-ins anyway.
            if name.startswith('__builtin__.'):
                name = name[12:]
            # Turn top-level class names into wiki links.
            if hasattr(sys.modules[modname], name):
                name = '[%s]' % name
            return name
        pydoc.classname = classname
        try:
            return pydoc.TextDoc.document(self, object,
                                          name, *args)
        finally:
            pydoc.classname = _classname
            pydoc.visiblename = _visiblename
        
    def bold(self, text):
        # Wiki bold.
        return '*%s*' % text

    def docclass(self, object, name=None, mod=None):
        # Exclude classes from the root module documentation.
        if mod is not None:
            return ''
        return pydoc.TextDoc.docclass(self, object, name, mod)


def make_wiki_doc(object, destdir='', name=None):
    '''Creates a .wiki file documenting the given object.
    If "name" is given, it is the name of the file without
    ".wiki". Otherwise object.__name__ is used.
    '''
    doc = WikiDoc().document(object)
    spacedlines = '\n'.join('%s ' % t for t in doc.splitlines())
    doc = '<pre>\n%s</pre>' % spacedlines
    if name is None:
        name = object.__name__
    path = os.path.join(destdir, '%s.wiki' % name)
    print 'writing %s' % path
    if not os.path.exists(destdir):
        os.makedirs(destdir)
    open(path, 'w').write(doc)


class wikidoc(Command):
    '''Handles the 'wikidoc' command.'''
    
    description = 'create the documentation .wiki files'
    user_options = [('destdir=', 'd', 'destination directory for the .wiki files')]
    
    def initialize_options(self):
        self.destdir = 'doc'
        
    def finalize_options(self):
        pass
    
    def run(self):
        make_wiki_doc(scribd, self.destdir)
        classes = inspect.getmembers(scribd, inspect.isclass)
        for name, class_ in classes:
            make_wiki_doc(class_, self.destdir, name)
    

# start the distutils setup
setup(name='scribd',
      version=scribd.__version__,
      description='Scribd client library for Python.',
      long_description='A library providing a high-level object oriented interface to the scribd.com website RESTful API.',
      author='Arkadiusz Wahlig',
      author_email='arkadiusz.wahlig@gmail.com',
      url='http://code.google.com/p/python-scribd',
      license='New BSD License',
      packages=['scribd'],
      package_data={'scribd': ['LICENSE']},
      provides=['scribd'],
      cmdclass={'wikidoc': wikidoc})
