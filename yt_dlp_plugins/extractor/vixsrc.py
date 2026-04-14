import re
import json
from urllib.parse import urljoin
from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import ExtractorError, update_url_query

class VixSrcIE(InfoExtractor):
    _VALID_URL = r'https?://(?:www\.)?vixsrc\.to/(?P<t>movie|tv)/(?P<i>[\w/]+)'

    def _real_extract(self, url):
        d, b = self._downloader, 'https://vixsrc.to'
        dw, sr = self._download_webpage, self._search_regex
        if d:
            d.params.update({'concurrent_fragment_downloads': 15, 'retries': 10, 'fragment_retries': 30})
            d.params.setdefault('retry_sleep', {})['fragment'] = 1.0

        t, i = self._match_valid_url(url).group('t', 'i')
        v_id, p = i.replace('/', '_'), i.split('/') + ['1', '1']
        
        tu = f'https://www.themoviedb.org/{t}/{p[0]}{f"/season/{p[1]}/episode/{p[2]}" if t == "tv" else ""}?language=it'
        tp = dw(tu, v_id, fatal=False) or ''
        title = re.sub(r'\s*(?:[-—]|&mdash;)\s*The Movie Database.*', '', self._html_search_regex(r'<title>(.+?)</title>', tp, 'title', default=v_id)).strip()

        h = {'Referer': f'{b}/'}
        
        # New API fetch logic
        api_url = url.replace('/tv/', '/api/tv/').replace('/movie/', '/api/movie/')
        api_resp = dw(api_url, v_id, headers=h, fatal=False, note='Fetching API JSON')
        
        target_fetch_url = url
        if api_resp:
            try:
                api_json = json.loads(api_resp)
                if 'src' in api_json:
                    target_fetch_url = urljoin(b, api_json['src'])
            except json.JSONDecodeError:
                pass

        wp = dw(target_fetch_url, v_id, headers={'Referer': url})
        
        tk = sr(r"['\"]token['\"]\s*:\s*['\"](\w+)['\"]", wp, 'token', default=None)
        
        # Fallback to legacy iframe parsing just in case API approach isn't available
        if not tk:
            wp_fallback = dw(url, v_id, headers=h, note='Downloading fallback webpage')
            for _ in range(3):
                tk = sr(r"['\"]token['\"]\s*:\s*['\"](\w+)['\"]", wp_fallback, 'token', default=None)
                if tk: 
                    wp = wp_fallback
                    break
                ip = sr(r'<iframe[^>]+src=["\']([^"\']+)["\']', wp_fallback, 'iframe', default=None)
                if not ip: break
                v = sr(r'data-page=["\'].*?"version"\s*:\s*"([^"]+)"', wp_fallback, 'version', default='')
                if v: h.update({'x-inertia': 'true', 'x-inertia-version': v})
                url_fallback = urljoin(url, ip)
                h['Referer'] = url_fallback
                wp_fallback = dw(url_fallback, v_id, headers=h, note='Downloading iframe')
                
        if not tk: raise ExtractorError('Stream not found')
        
        raw_url = sr(r"(?:['\"]url['\"]|url)\s*:\s*['\"]([^'\"]+)['\"]", wp, 'url').replace('\\/', '/')
        su = re.sub(r'(/playlist/[^/?]+)(?!\.m3u8)(?=[?#]|$)', r'\1.m3u8', raw_url)
        q = {'token': tk, 'expires': sr(r"['\"]expires['\"]\s*:\s*['\"](\d+)['\"]", wp, 'expires')}
        if re.search(r'canPlayFHD\s*=\s*true', wp): q['h'] = '1'

        return {
            'id': v_id, 'title': title,
            'formats': self._extract_m3u8_formats(update_url_query(su, q), v_id, 'mp4', m3u8_id='hls', fatal=True, headers={'Referer': url, 'Origin': b}),
            'http_headers': {'Referer': url, 'Origin': b, 'Connection': 'keep-alive'}
        }
