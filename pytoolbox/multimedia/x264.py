# -*- coding: utf-8 -*-

#**********************************************************************************************************************#
#                                        PYTOOLBOX - TOOLBOX FOR PYTHON SCRIPTS
#
#  Main Developer : David Fischer (david.fischer.ch@gmail.com)
#  Copyright      : Copyright (c) 2012-2014 David Fischer. All rights reserved.
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

import re, select, shlex, time
from subprocess import Popen, PIPE
from .ffprobe import get_media_duration
from ..datetime import datetime_now, secs_to_time, time_ratio, total_seconds
from ..filesystem import get_size
from ..subprocess import make_async

# [79.5%] 3276/4123 frames, 284.69 fps, 2111.44 kb/s, eta 0:00:02
ENCODING_REGEX = re.compile(
    r'\[(?P<percent>\d+\.\d*)%\]\s+(?P<frame>\d+)/(?P<frame_total>\d+)\s+frames,\s+'
    r'(?P<fps>\d+\.\d*)\s+fps,\s+(?P<bitrate>[^,]+),\s+eta\s+(?P<eta>[\d:]+)'
)


def encode(in_filename, out_filename, encoder_string, default_in_duration='00:00:00', ratio_delta=0.01, time_delta=1,
           max_time_delta=5, sanity_min_ratio=0.95, sanity_max_ratio=1.05, executable='x264'):

    # Get input media duration and size to be able to estimate ETA
    in_duration = get_media_duration(in_filename) or default_in_duration
    in_duration_secs = total_seconds(in_duration)
    in_size = get_size(in_filename)
    out_filename = out_filename or '/dev/null'

    # Initialize metrics
    output = ''
    stats = {}
    start_date, start_time = datetime_now(), time.time()
    prev_ratio = prev_time = ratio = 0

    # Create x264 subprocess
    cmd = '{0} {1} -o "{2}" "{3}"'.format(executable, encoder_string, out_filename, in_filename)
    x264 = Popen(shlex.split(cmd), stderr=PIPE, close_fds=True)
    make_async(x264.stderr)

    while True:
        # Wait for data to become available
        select.select([x264.stderr], [], [])
        chunk = x264.stderr.read()
        output += chunk
        elapsed_time = time.time() - start_time
        match = ENCODING_REGEX.match(chunk)
        if match:
            stats = match.groupdict()
            out_duration = secs_to_time(in_duration_secs * float(stats['percent']))
            ratio = float(stats['frame']) / float(stats['frame_total'])
            delta_time = elapsed_time - prev_time
            if (ratio - prev_ratio > ratio_delta and delta_time > time_delta) or delta_time > max_time_delta:
                prev_ratio, prev_time = ratio, elapsed_time
                yield {
                    # FIXME report frame_total ?
                    'status': 'PROGRESS',
                    'output': output,
                    'returncode': None,
                    'start_date': start_date,
                    'elapsed_time': elapsed_time,
                    'eta_time': total_seconds(stats['eta']),
                    'in_size': in_size,
                    'in_duration': in_duration,
                    'out_size': get_size(out_filename),
                    'out_duration': out_duration,
                    'percent': float(stats['percent']),
                    'frame': int(stats['frame']),
                    'fps': float(stats['fps']),
                    'bitrate': stats['bitrate'],
                    'quality': None,  # FIXME
                    'sanity': None
                }
        returncode = x264.poll()
        if returncode is not None:
            break

    # Output media file sanity check
    out_duration = get_media_duration(out_filename)
    ratio = time_ratio(out_duration, in_duration) if out_duration else 0.0
    yield {
        # FIXME report frame_total ?
        'status': 'ERROR' if returncode else 'SUCCESS',
        'output': output,
        'returncode': returncode,
        'start_date': start_date,
        'elapsed_time': elapsed_time,
        'eta_time': 0,
        'in_size': in_size,
        'in_duration': in_duration,
        'out_size': get_size(out_filename),
        'out_duration': out_duration,
        'percent': float(stats.get('percent', 0)) if returncode else 100,  # Assume that a successful encoding = 100%
        'frame': int(stats.get('frame', 0)),
        'fps': float(stats.get('fps', 0)),
        'bitrate': stats.get('bitrate'),
        'quality': None,  # FIXME
        'sanity': sanity_min_ratio <= ratio <= sanity_max_ratio
    }
