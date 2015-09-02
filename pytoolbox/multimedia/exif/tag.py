# -*- encoding: utf-8 -*-

#**********************************************************************************************************************#
#                                        PYTOOLBOX - TOOLBOX FOR PYTHON SCRIPTS
#
#  Main Developer : David Fischer (david.fischer.ch@gmail.com)
#  Copyright      : Copyright (c) 2012-2015 David Fischer. All rights reserved.
#
#**********************************************************************************************************************#
#
# This file is part of David Fischer's pytoolbox Project.
#
# This project is free software: you can redistribute it and/or modify it under the terms of the EUPL v. 1.1 as provided
# by the European Commission. This project is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# See the European Union Public License for more details.
#
# You should have received a copy of the EUPL General Public License along with this project.
# If not, see he EUPL licence v1.1 is available in 22 languages:
#     22-07-2013, <https://joinup.ec.europa.eu/software/page/eupl/licence-eupl>
#
# Retrieved from https://github.com/davidfischer-ch/pytoolbox.git

from __future__ import absolute_import, division, print_function, unicode_literals

import datetime
from fractions import Fraction

from . import brand
from ... import decorators, module
from ...datetime import str_to_datetime, str_to_time
from ...encoding import string_types

_all = module.All(globals())


class Tag(object):

    brand_class = brand.Brand
    date_formats = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d']
    group_to_brand_blacklist = frozenset(['aux', 'crs', 'Image', 'Photo'])
    type_to_hook = {
        datetime.datetime: 'get_tag_string',  # clean method will convert to a date-time
        datetime.time: 'get_tag_string',  # clean method will convert to a time
        Fraction: 'get_exif_tag_rational',
        int: 'get_tag_long',
        list: 'get_tag_multiple',
        str: 'get_tag_string'
    }
    type_to_python = {
        'Ascii': str,
        'Byte': bytes,
        'Comment': str,
        'Date': datetime.datetime,
        'LangAlt': str,
        'Long': int,
        'Rational': Fraction,
        'SRational': Fraction,
        'SLong': int,
        'Short': int,
        'SShort': int,
        'String': str,
        'Time': datetime.time,
        'Undefined': bytes,
        'XmpBag': list,
        'XmpSeq': list,
        'XmpText': str
    }

    def __init__(self, metadata, key):
        self.metadata = metadata
        self.key = key

    def __repr__(self):
        return '<{0.__class__.__name__} {0.key}: {1}>'.format(self, str(self.data)[:20])

    @property
    def data(self):
        type_hook = self.get_type_hook()
        if type_hook:
            try:
                return self.clean(type_hook(self.key))
            except UnicodeDecodeError as e:
                return e
        return self.data_bytes

    @property
    def data_bytes(self):
        tag_raw = self.metadata.exiv2.get_tag_raw(self.key)
        return tag_raw.get_data() if tag_raw else None

    @decorators.cached_property
    def description(self):
        return self.metadata.exiv2.get_tag_description(self.key)

    @property
    def brand(self):
        if self.group not in self.group_to_brand_blacklist:
            return self.brand_class(self.group)

    @property
    def group(self):
        return self.key.split('.')[-2]

    @decorators.cached_property
    def label(self):
        return self.metadata.exiv2.get_tag_label(self.key) or self.key.split('.')[-1]

    @property
    def size(self):
        return self.metadata.exiv2.get_tag_raw(self.key).get_size()

    @decorators.cached_property
    def type(self):
        tag_type = self.metadata.exiv2.get_tag_type(self.key)
        try:
            return self.type_to_python[tag_type]
        except KeyError:
            if tag_type:
                raise KeyError('Unknow tag type {0}'.format(tag_type))
        return bytes

    def clean(self, data):
        if isinstance(data, string_types):
            data = data.strip()
        if self.type == datetime.time:
            return str_to_time(data)
        elif self.type == datetime.datetime or isinstance(data, string_types):
            for date_format in self.date_formats:
                date = str_to_datetime(data, date_format, fail=False)
                if date:
                    return date
        assert not data or isinstance(data, self.type), '{0.key} {0.type} {1} {2}'.format(self, data, type(data))
        return data

    def get_type_hook(self):
        name = self.type_to_hook.get(self.type)
        return getattr(self.metadata.exiv2, name) if name else None


class TagSet(object):

    @staticmethod
    def clean_number(number):
        return number if number and number > 0 else None

    def __init__(self, metadata):
        self.metadata = metadata

__all__ = _all.diff(globals())
