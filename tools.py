# -*- coding: utf-8 -*-
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import unicodedata

src_chars = "/*+?Â¿!$[]{}@#`^:;<>=~%\\"
dst_chars = "________________________"


def normalize(text):
    if isinstance(text, str):
        text = text.encode('utf-8')
    return text


def unaccent(text):
    output = text
    for c in range(len(src_chars)):
        if c >= len(dst_chars):
            break
        output = output.replace(src_chars[c], dst_chars[c])
    output = unicodedata.normalize('NFKD', output).encode('ASCII',
        'ignore')
    return output.replace(b"_",b"")
