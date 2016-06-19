# flake8: NOQA
import sys

PY2 = sys.version_info[0] == 2

_identity = lambda x: x


if PY2:
    unichr = unichr
    text_type = unicode
    string_types = (str, unicode)
    from urllib import urlretrieve

    iterkeys = lambda d: d.iterkeys()
    itervalues = lambda d: d.itervalues()
    iteritems = lambda d: d.iteritems()

    from cStringIO import StringIO as BytesIO
    from StringIO import StringIO
    import cPickle as pickle
    import ConfigParser as configparser

    cmp = cmp

    input = raw_input
    from string import lower as ascii_lowercase
    import urlparse

    def console_to_str(s):
        return s.decode('utf_8')

else:
    unichr = chr
    text_type = str
    string_types = (str,)

    iterkeys = lambda d: iter(d.keys())
    itervalues = lambda d: iter(d.values())
    iteritems = lambda d: iter(d.items())

    from io import StringIO, BytesIO
    import pickle
    import configparser

    cmp = lambda a, b: (a > b) - (a < b)

    input = input
    from string import ascii_lowercase
    import urllib.parse as urllib
    import urllib.parse as urlparse
    from urllib.request import urlretrieve

    from test import support

    console_encoding = sys.__stdout__.encoding

    def console_to_str(s):
        """ From pypa/pip project, pip.backwardwardcompat. License MIT. """
        try:
            return s.decode(console_encoding)
        except UnicodeDecodeError:
            return s.decode('utf_8')
        except AttributeError:  # for tests, #13
            return s
