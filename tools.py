# -*- coding: utf-8 -*-
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import unicodedata

src_chars = u"/*+?Â¿!$[]{}@#`^:;<>=~%\\"
dst_chars = u"________________________"


def normalize(text):
    if isinstance(text, unicode):
        text = text.encode('utf-8')
    return text


def unaccent(text):
    if isinstance(text, bytes):
        text = unicode(text, 'utf-8')
    output = text
    for c in xrange(len(src_chars)):
        if c >= len(dst_chars):
            break
        output = output.replace(src_chars[c], dst_chars[c])
    output = unicodedata.normalize('NFKD', output).encode('ASCII',
        'ignore')
    return output.strip('_').encode('utf-8')
