import re
from urllib.parse import urljoin
from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import ExtractorError, update_url_query

class VixSrcIE(InfoExtractor):
    _VALID_URL = r'https?://(?:www\.)?vixsrc\.to/(?P<t>movie|tv)/(?P<i>[\w/]+)'

    def _real_extract(self, url):
        d, b = self._downloader, 'https://vixsrc.to'
        dw, sr = self._download_webpage, self._search_regex
        if d:
            d.params.update({'concurrent_fragment_downloads': 16, 'retries': 10, 'fragment_retries': 30})
            d.params.setdefault('retry_sleep', {})['fragment'] = 1.0

        t, i = self._match_valid_url(url).group('t', 'i')
        v_id, p = i.replace('/', '_'), i.split('/') + ['1', '1']
        
        tu = f'https://www.themoviedb.org/{t}/{p[0]}{f"/season/{p[1]}/episode/{p[2]}" if t == "tv" else ""}?language=it'
        tp = dw(tu, v_id, fatal=False) or ''
        title = re.sub(r'\s*(?:[-—]|&mdash;)\s*The Movie Database.*', '', self._html_search_regex(r'<title>(.+?)</title>', tp, 'title', default=v_id)).strip()

        h = {'Referer': f'{b}/'}
        wp = dw(url, v_id, headers=h)
        
        for _ in range(3):
            tk = sr(r"['\"]token['\"]\s*:\s*['\"](\w+)['\"]", wp, 'token', default=None)
            if tk: break
            ip = sr(r'<iframe[^>]+src=["\']([^"\']+)["\']', wp, 'iframe', default=None)
            if not ip: break
            v = sr(r'data-page=["\'].*?"version"\s*:\s*"([^"]+)"', wp, 'version', default='')
            if v: h.update({'x-inertia': 'true', 'x-inertia-version': v})
            url = urljoin(url, ip)
            h['Referer'] = url
            wp = dw(url, v_id, headers=h, note='Downloading iframe')

        if not tk: raise ExtractorError('Stream not found')
        
        su = re.sub(r'(/playlist/[^/?]+)(?!\.m3u8)(?=[?#]|$)', r'\1.m3u8', sr(r"(?:['\"]url['\"]|url)\s*:\s*['\"]([^'\"]+)['\"]", wp, 'url'))
        q = {'token': tk, 'expires': sr(r"['\"]expires['\"]\s*:\s*['\"](\d+)['\"]", wp, 'expires')}
        if re.search(r'canPlayFHD\s*=\s*true', wp): q['h'] = '1'

        return {
            'id': v_id, 'title': title,
            'formats': self._extract_m3u8_formats(update_url_query(su, q), v_id, 'mp4', m3u8_id='hls', fatal=True, headers={'Referer': url, 'Origin': b}),
            'http_headers': {'Referer': url, 'Origin': b, 'Connection': 'keep-alive'}
        }