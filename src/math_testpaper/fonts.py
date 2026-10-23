from __future__ import annotations
import hashlib
import os
from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from .model import ExamError, read_json

ASSETS = Path(__file__).parent / 'assets'

def register_fonts(profile='auto', custom=None):
    windows = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
    hy = {'body': windows/'H2MJSM.TTF', 'head': windows/'H2MJRE.TTF', 'title': windows/'H2GTRE.TTF'}
    if custom:
        custom = Path(custom).resolve(); data = read_json(custom)
        paths = {k: (custom.parent / data[k]).resolve() for k in ('body','head','title')}
        selected = 'custom'
    else:
        if profile == 'auto': profile = 'hy' if all(p.is_file() for p in hy.values()) else 'nanum'
        if profile == 'hy': paths = hy
        elif profile == 'nanum':
            paths = {'body': ASSETS/'fonts/NanumMyeongjo-Regular.ttf', 'head': ASSETS/'fonts/NanumMyeongjo-Bold.ttf', 'title': ASSETS/'fonts/NanumGothic-Bold.ttf'}
        else: raise ExamError('Unknown font profile: ' + profile)
        selected = profile
    names = {}; records = {}
    for role, path in paths.items():
        if not path.is_file(): raise ExamError(f'Missing {role} font: {path}; use --font-profile nanum or --fonts')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        name = 'Exam_' + role + '_' + digest[:12]
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(path)))
        names[role] = name; records[role] = {'file':path.name, 'sha256':digest}
    return names, {'profile':selected, 'fonts':records}
