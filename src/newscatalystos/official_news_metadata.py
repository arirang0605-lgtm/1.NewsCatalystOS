"""Read only titles and document IDs from the reviewed public news listing.

No scripts, article pages, summaries, images or body text are executed/stored.
The registry restricts this adapter to a reviewed official company listing.
"""
from html.parser import HTMLParser
import re

from .source_share import SourceShareError

BASE='https://www.hd-hyundaielectric.com/elect/ko/PR/'
ENDPOINT=re.compile(re.escape(BASE)+r'newsList\.jsp(?:\?paging\.pageNo=[1-3])?\Z')


def parse_listing(payload):
    if not isinstance(payload,bytes) or not 0 < len(payload) <= 1024*1024:
        raise SourceShareError('bounded official metadata listing required')
    class Listing(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.current=None
            self.parts=[]
            self.rows={}
        def handle_starttag(self,tag,attrs):
            if tag!='a':return
            attrs=dict(attrs)
            match=re.fullmatch(r"(?:javascript:)?goDetail\('([0-9]{1,10})'\);?",attrs.get('onclick',''))
            self.current=match[1] if match else None
            self.parts=[]
        def handle_data(self,text):
            if self.current:self.parts.append(text)
        def handle_endtag(self,tag):
            if tag!='a' or self.current is None:return
            title=re.sub(r'\s+',' ',''.join(self.parts)).strip()
            if title:
                previous=self.rows.get(self.current)
                if previous is not None and previous!=title:
                    raise SourceShareError('ambiguous official news document title')
                self.rows[self.current]=title
                if len(self.rows)>100:raise SourceShareError('official metadata item limit')
            self.current=None
    try:
        parser=Listing()
        parser.feed(payload.decode('utf-8'))
        parser.close()
    except (UnicodeDecodeError,ValueError) as exc:
        raise SourceShareError('invalid official listing encoding') from exc
    if not parser.rows:raise SourceShareError('official news listing layout unavailable')
    return [(key,title,BASE+'newsView.jsp?commBoardSeq='+key)
            for key,title in parser.rows.items()]
