#!/usr/bin/env python
"""
Scribd client library distutils setup script.

Copyright (c) 2009, Arkadiusz Wahlig <arkadiusz.wahlig@gmail.com>

Distributed under the BSD License, see the
accompanying LICENSE file for more information.
"""

import sys
import os
import pydoc
import inspect
import re
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
        # \xff will be replaced with '*' later.
        return '\xff%s\xff' % text

    def indent(self, text, prefix='    '):
        return pydoc.TextDoc.indent(self, text)
        
    def section(self, title, contents):
        if title == 'FILE':
            # Remove the path part.
            contents = os.path.basename(contents)
        return pydoc.TextDoc.section(self, title, contents)

    def docclass(self, object, name=None, mod=None):
        # Exclude classes from the root module documentation.
        if mod is not None:
            return ''
        return pydoc.TextDoc.docclass(self, object, name, mod)

    def docother(self, object, name=None, mod=None, parent=None, maxlen=None, doc=None):
        text = pydoc.TextDoc.docother(self, object, name, mod, parent, maxlen, doc)
        rep = repr(object)
        pos = rep.find(' at 0x')
        if rep.startswith('<') and pos > 0 and rep.endswith('>'):
            # Object has an unsuitable representation.
            fin = pos + 6
            while rep[fin].isalnum():
                fin += 1
            rep = rep[:pos] + rep[fin:]
            if hasattr(object, '__class__') and object.__class__.__module__ == mod:
                name = object.__class__.__name__
                rep = rep.replace(name, '[%s]' % name)
            text = text[:text.index('<')] + rep
        return text


def make_wiki_doc(object, destdir='', name=None):
    """Creates a .wiki file documenting the given object.
    
    If "name" is given, it is the name of the file without
    ".wiki". Otherwise object.__name__ is used.
    """
    doc = WikiDoc().document(object)
    # Add a space to all lines.
    text = '\n'.join('%s ' % t for t in doc.splitlines())
    # Surround all underscores with backtick but only if not surrounded by alnums.
    text = re.sub(r'[a-zA-Z0-9]_[a-zA-Z0-9]', lambda m: m.group(0).replace('_', '\x01'),
                  text).replace('_', '`_`').replace('\x01', '_')
    # Same for a star.
    text = re.sub(r'[a-zA-Z0-9]*[a-zA-Z0-9]', lambda m: m.group(0).replace('*', '\x01'),
                  text).replace('*', '`*`').replace('\x01', '*')
    # Fix the bolds added by WikiDoc class.
    text = text.replace('\xff', '*')
    text = '<pre>\n%s</pre>' % text
    if name is None:
        name = object.__name__
    path = os.path.join(destdir, '%s.wiki' % name)
    print 'writing %s' % path
    if not os.path.exists(destdir):
        os.makedirs(destdir)
    open(path, 'w').write(text)


class wikidoc(Command):
    """Handles the 'wikidoc' command."""
    
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
