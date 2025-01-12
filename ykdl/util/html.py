#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
from logging import getLogger
from ykdl.compact import Request, urlopen, install_opener, build_opener

from .match import match1


logger = getLogger("html")

default_handlers = []

def add_default_handler(handler):
    if isinstance(handler, type):
        handler = handler()
    remove = []
    for default_handler in default_handlers:
        if isinstance(handler, type(default_handler)) or isinstance(default_handler, type(handler)):
            remove.append(default_handler)
    for _handler in remove:
        default_handlers.remove(_handler)
        logger.debug('Remove %s from default handlers' % _handler)
    default_handlers.append(handler)
    logger.debug('Add %s to default handlers' % handler)

def install_default_handlers():
    install_opener(build_opener(*default_handlers))

fake_headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:38.0) Gecko/20100101 Firefox/38.0 Iceweasel/38.2.1',
    "cookie": 'dy_did=9cb262eb4e5fd753b793dd3a00021501; dy_did=9cb262eb4e5fd753b793dd3a00021501; PHPSESSID=pvbps1dveuqafagi0j98073030; acf_auth=d7fb6A090ExVkxjk5WiPo38LKSuoAQhhwHNJivOXNkezzVeIVwQoRQp3J1wGPOhLAL3hm3yM7ATJCY8jQ4mNQ3QCiWf04WPsU4Gpd7oT6Ir63g2r04KPxxM9Zb2EVQ; acf_jwt=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE2MTU3NDI1NzEsInUiOjExMjg4ODE1LCJubiI6ImN0MTAyNiIsInN0IjoiZWFlYmMwNjlkM2JjYmYzYyIsImN0IjoiMCIsImx0IjoiNjQ2MjQ3NzgiLCJidCI6IjYiLCJ0IjoxNjE1MjEzMzcxfQ.8ul9U1VJzXCd6tC4U4byEEd8DHldPFqInAzNnsMPbyQ; acf_uid=11288815; acf_username=auto_Ax5bhBO9qw; acf_nickname=ct1026; acf_own_room=0; acf_groupid=1; acf_phonestatus=1; acf_ct=0; acf_ltkid=64624778; acf_biz=6; acf_stk=eaebc069d3bcbf3c; acf_avatar=//apic.douyucdn.cn/upload/avatar/011/28/88/15_avatar_'
}

fake_headers_without_ae = fake_headers.copy()
del fake_headers_without_ae['Accept-Encoding']

def add_header(key, value):
    global fake_headers, fake_headers_without_ae
    fake_headers[key] = value
    if key != 'Accept-Encoding':
        fake_headers_without_ae[key] = value

def unicodize(text):
    return re.sub(r'\\u([0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f])', lambda x: chr(int(x.group(0)[2:], 16)), text)

def ungzip(data):
    """Decompresses data for Content-Encoding: gzip.
    """
    from io import BytesIO
    import gzip
    buffer = BytesIO(data)
    f = gzip.GzipFile(fileobj=buffer)
    return f.read()

def undeflate(data):
    """Decompresses data for Content-Encoding: deflate.
    (the zlib compression is used.)
    """
    import zlib
    decompressobj = zlib.decompressobj(-zlib.MAX_WBITS)
    return decompressobj.decompress(data)+decompressobj.flush()

def get_head_response(url, headers=fake_headers):
    try:
        req = Request(url, headers=headers)
        req.get_method = lambda: 'HEAD'
        response = urlopen(req)
    except IOError as e:
        # if HEAD method is not supported
        if 'HTTP Error 405' in str(e):
            req = Request(url, headers=headers)
            response = urlopen(req)
            response.close()
        else:
            raise
    # urllib will follow redirections and it's too much code to tell urllib
    # not to do that
    return response

def get_location(url, headers=fake_headers):
    response = get_head_response(url, headers=headers)
    return response.geturl()

def get_location_and_header(url, headers=fake_headers):
    response = get_head_response(url, headers=headers)
    return response.geturl(), response.info()

def get_content(url, headers=fake_headers, data=None, charset=None):
    """Gets the content of a URL via sending a HTTP GET request.

    Args:
        url: A URL.
        headers: Request headers used by the client.
        decoded: Whether decode the response body using UTF-8 or the charset specified in Content-Type.

    Returns:
        The content as a string.
    """
    logger.debug("get_content> URL: " + url)
    req = Request(url, headers=headers, data=data)
    #if cookies_txt:
    #    cookies_txt.add_cookie_header(req)
    #    req.headers.update(req.unredirected_hdrs)
    response = urlopen(req)
    data = response.read()

    # Handle HTTP compression for gzip and deflate (zlib)
    resheader = response.info()
    if 'Content-Encoding' in resheader:
        content_encoding = resheader['Content-Encoding']
    elif hasattr(resheader, 'get_payload'):
        payload = resheader.get_payload()
        if isinstance(payload, str):
            content_encoding =  match1(payload, r'Content-Encoding:\s*([\w-]+)')
        else:
            content_encoding = None
    else:
        content_encoding = None
    if content_encoding == 'gzip':
        data = ungzip(data)
    elif content_encoding == 'deflate':
        data = undeflate(data)

    if charset == 'ignore':
        return data

    # Decode the response body
    if charset is None:
        if 'Content-Type' in resheader:
            charset = match1(resheader['Content-Type'], r'charset=([\w-]+)')
        charset = charset or match1(str(data), r'charset=\"([\w-]+)', 'charset=([\w-]+)') or 'utf-8'
    logger.debug("get_content> Charset: " + charset)
    try:
        data = data.decode(charset, errors='replace')
    except:
        logger.warning("wrong charset for {}".format(url))
    return data

#DEPRECATED below, return None or 0
def url_size(url, faker=False):
    return 0

def urls_size(urls):
    return sum(map(url_size, urls))

def url_info(url, faker=False):
    # in case url is http(s)://host/a/b/c.dd?ee&fff&gg
    # below is to get c.dd
    f = url.split('?')[0].split('/')[-1]
    # check . in c.dd, get dd if true
    if '.' in f:
        ext = f.split('.')[-1]
    else:
        ext = ""
    return '', ext, 0
