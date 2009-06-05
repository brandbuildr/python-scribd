'''This module provides a simplified interface to the
xml.dom.minidom objects. It supports a limited subset
of its features and is meant for very simple xml
files only.

Copyright (c) 2009 Arkadiusz Wahlig <arkadiusz.wahlig@gmail.com>
'''

from xml.dom import minidom


class Element(object):
    '''Encapsulates a single minidom element. Provides a list/dict-like
    index and get methods. If the element contains text/cdata only, it
    has no subelements and the text is available as the "text" attribute.
    Element attributes are available in attrs dictionary.
    '''

    def __init__(self, element):
        self._element = element
        self.name = str(element.tagName)
        self.text = None
        nodes = element.childNodes
        if len(nodes) == 1 and nodes[0].nodeType == element.TEXT_NODE:
            self.text = nodes[0].data.strip()
            self._nodes = []
        else:
            self._nodes = [node for node in nodes if node.nodeType != element.TEXT_NODE]
        if len(self._nodes) == 1 and self._nodes[0].nodeType == \
                                     element.CDATA_SECTION_NODE:
            self.text = self._nodes[0].data.strip()
            self._nodes = []
        self.attrs = {}
        for name, value in element.attributes.items():
            self.attrs[name] = value

    def index(self, name):
        '''Returns an index of the first subelement with the given name.
        Raises an IndexError if not found.
        '''
        for i, c in enumerate(self._nodes):
            if str(c.tagName) == name:
                return i
        raise IndexError('%s is not in the sub-tags' % name)

    def get(self, name):
        '''Returns the first subelement with the given name.
        Raises a KeyError if not found.
        '''
        try:
            return Element(self._nodes[self.index(name)])
        except IndexError:
            raise KeyError('%s is not in the sub-tags' % name)

    def toxml(self):
        '''Returns the element and all subelements as xml.
        '''
        return self._element.toxml()

    def __getitem__(self, i):
        '''Returns the subelement at given index.
        Raises an IndexError if index out of range.
        '''
        return Element(self._nodes[i])

    def __len__(self):
        '''Returns the number of subelements.
        '''
        return len(self._nodes)
        
    def __contains__(self, name):
        '''Tests if given element can be found in the subelements.
        '''
        try:
            self.index(name)
        except IndexError:
            return False
        return True

    def __repr__(self):
        text = ''
        if self.text is not None:
            text = ', text=%s' % repr(self.text)
        return '<%s.%s %s at 0x%x%s>' % (self.__class__.__module__,
               self.__class__.__name__, repr(self.name), id(self), text)


def parse(xml):
    '''Parses an xml and returns the Element object of the root element.
    xml may be either a string or a file-alike object.
    '''
    if isinstance(xml, str):
        dom = minidom.parseString(xml)
    else:
        dom = minidom.parse(xml)
    return Element(dom.documentElement)
