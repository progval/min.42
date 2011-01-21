# -*- coding: utf8 -*-

# Copyright (c) 2010, Valentin Lorentz
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution.
# * Neither the name of the University of California, Berkeley nor the
# names of its contributors may be used to endorse or promote products
# derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE REGENTS AND CONTRIBUTORS ``AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE REGENTS AND CONTRIBUTORS BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import time
from common import db
from common import html
from common import exceptions

HOUR = 3600

def run(environ):
    headers = []
    status = '200 OK'
    tiny = environ['module_path'].split('/')[0]
    try:
        assert tiny != ''
    except:
        raise exceptions.Error404()
    cursor = db.conn.cursor()
    cursor.execute('SELECT `full` FROM `tiny2full` WHERE tiny=?', (tiny,))
    result = cursor.fetchone()
    if result is None:
        raise exceptions.Error404()
    longurl = result[0]
    results = []

    for start, end in [(x-HOUR,x) for x in
                       [int(x)+time.time() for x in
                        range(0, 12*HOUR, HOUR)]]:
        cursor.execute("""SELECT COUNT(*) FROM `clicks`
                          WHERE `tiny`=? AND `time`>? AND `time`<?""",
                       (tiny, start, end))
        results.append(cursor.fetchone()[0])

    max_ = max(results)
    min_ = min(results)

    table = '<table>'
    for ago, number in zip(range(1, 12), results):
        if ago >= 2:
            ago = 'Il y a %i heures' % ago
        elif ago == 1:
            ago = u'La dernière heure'
        table += '<tr><td>%s</td><td>%i</td></tr>' % (ago, number)
    table += '</table>'

    responseBody = html.getHead(title='Statistiques sur %s' % tiny)
    responseBody += u'Statistiques de clics pour l\'URL raccourcie.'
    responseBody += table
    responseBody += html.getFoot()

    return status, headers, responseBody

