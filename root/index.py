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

from common.lib.pesto import cookie as cookielib
from common import exceptions
from common import parsers
from common import errors
from common import html
from common import user
from common import db
import hashlib
import random
import time
import re

matchUrl1 = re.compile('^([a-zA-Z_-]+\.)+[a-z0-9]{2,4}(:[0-9]+)?(/.*)?$')
matchUrl2 = re.compile('^[a-z]+://([a-zA-Z_-]+\.)+[a-z0-9]{2,4}(:[0-9]+)?(/.*)?$')

rootTemplate = u"""
Bienvenue sur <a href="http://min.42/">min.42</a>
<hr />
Vos dernières URLs raccourcies :
<ul>
    %(last_tiny)s
</ul>
<hr />
<form action="submiturl.htm" method="post">
    <table>
        <tr>
            <td>
                <input type="text" name="longurl" id="longurl" />
            </td>
            <td>
                <label for="longurl">URL à raccourcir</label>
            </td>
        </tr>
        <tr>
            <td>
                <input type="text" name="size" id="size" />
            </td>
            <td>
                <label for="size">Longueur de l'ID de l'URL courte</label>
                <br />
                Un ID plus court donnera une URL plus courte, mais aura une
                durée de vie garantie plus courte.<br />
                La taille peut varier de 2 à 7 (inclus)
            </td>
        </tr>
    </table>

    <input type="submit" value="Raccourcir" />
</form>
"""

lifetimes = {1:60,
             2:10*60,
             3:60*60,
             4:24*60*60,
             5:7*24*60*60,
             6:30*24*30*30,
             7:0}
def getExpiry(size):
    assert size in lifetimes
    lifetime = lifetimes[size]
    if lifetime == 0: # infinite
        return 0
    else:
        return time.time() + lifetime


def run(environ):
    headers = []
    status = '200 OK'
    if environ['module_path'] == '':
        responseBody = html.getHead(title='Accueil')


        cursor = db.conn.cursor()
        cursor.execute("""SELECT `tiny`, `full` FROM `tiny2full`
                          WHERE `u_id`=?
                          ORDER BY `submit_time` DESC
                          LIMIT 0,20""", (user.currentUser.id,))
        older = time.time() - 60*60
        string = ''
        for tiny, full in cursor:
            string += '<li><a href="/%s">%s</a> ' % (tiny, full)
            string += '<a href="/stats/%s">Stats</a></li>' % tiny
        responseBody += rootTemplate % {'last_tiny': string}


        cursor = db.conn.cursor()
        cursor.execute('SELECT `full` FROM `tiny2full`')


        responseBody += html.getFoot()
        return status, headers, responseBody
    elif environ['module_path'] == 'submiturl.htm':
        errormsg = ''

        data = parsers.http_query(environ, 'POST')
        assert all((key in data) for key in ('longurl','size'))

        longurl, size = data['longurl'], data['size']

        if matchUrl1.match(longurl):
            longurl = 'http://' + longurl
        elif not matchUrl2.match(longurl):
            errormsg += u'<p>Votre URL longue ne correspond pas à notre ' + \
                        u'expression régulière.</p>'
        try:
            size = int(size)
            assert 2 <= size <= 7
        except:
            errormsg += u'<p>La taille ne peut être qu\'un entier ' + \
                        u'positif compris entre 2 et 7 (inclus)</pre>'
        if errormsg != '':
            responseBody = html.getHead(title='Nouvelle URL - Erreur')
            responseBody += errormsg
            responseBody += html.getFoot()
            return status, headers, responseBody

        hash_ = hashlib.md5(longurl)
        tiny = ''
        timeout = time.time() + 0.5
        cursor = db.conn.cursor()
        while tiny == '' and time.time() < timeout:
            digest = hash_.hexdigest()
            while len(digest) >= size:
                cursor.execute("""SELECT `full`, `expiry` FROM `tiny2full`
                                  WHERE `tiny`=?""", (digest[0:size],))
                result = cursor.fetchone()
                if result is None or (result[1]!=0 and result[1]<time.time()):
                    tiny=digest[0:size]
                    if result is not None:
                        cursor.execute("""DELETE FROM `tiny2full`
                                          WHERE `tiny`=?""", (tiny,))
                    cursor.execute('INSERT INTO `tiny2full` VALUES(?,?,?,?,?)',
                                   (tiny, user.currentUser.id, longurl,
                                    getExpiry(size), time.time()))
                    db.conn.commit()
                    break
                if result[0] == longurl:
                    tiny = digest[0:size]
                    break
                digest = digest[1:] # Strip the first character
            hash_.update(chr(random.randrange(255)))

        assert tiny != '', ('Impossible de calculer une URL raccourcie,'
                            'veuillez réessayer (un facteur aléatoire '
                            'intervient dans le calcul)')

        responseBody = u'<a href="/">Cliquez sur ce lien si vous n\'êtes ' + \
                       u'pas redirigé(e)</a>'
        headers.append(('Location', '/'))
        status = '302 Found'
    else:
        cursor = db.conn.cursor()
        cursor.execute('SELECT `full` FROM `tiny2full` WHERE `tiny`=?',
                       (environ['module_path'],))
        result = cursor.fetchone()
        if result is None:
            raise exceptions.Error404()

        cursor = db.conn.cursor()
        cursor.execute("""INSERT INTO `clicks` VALUES(?,?,?)""",
                       (environ['module_path'], user.currentUser.id, int(time.time())))
        db.conn.commit()
        cursor.execute('SELECT * FROM `clicks`')

        responseBody = (u'<a href="%s">Cliquez sur ce lien si vous n\'êtes '
                       u'pas redirigé(e)</a>') % result[0]
        headers.append(('Location', str(result[0])))
        status = '302 Found'


    return status, headers, responseBody
