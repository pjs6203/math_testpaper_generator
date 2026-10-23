from __future__ import annotations
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from xml.etree import ElementTree as ET
from reportlab.graphics.svgpath import SvgPath
from .model import ExamError, formulae, read_json, write_json

BRIDGE = Path(__file__).with_name('_math.cjs')

def node_environment():
    env = os.environ.copy(); paths = []
    if env.get('MATH_TESTPAPER_NODE_MODULES'): paths.append(env['MATH_TESTPAPER_NODE_MODULES'])
    paths.append(str(Path.cwd()/'node_modules'))
    paths += [str(p/'node_modules') for p in Path(__file__).resolve().parents]
    if env.get('NODE_PATH'): paths.append(env['NODE_PATH'])
    env['NODE_PATH'] = os.pathsep.join(paths)
    return env

def run_node(*args):
    node = shutil.which('node')
    if not node: raise ExamError('Node.js 20+ is missing. Install Node.js, then run npm ci in this repository.')
    try:
        result = subprocess.run([node, str(BRIDGE), *map(str,args)], env=node_environment(), capture_output=True, text=True, encoding='utf8', timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ExamError(f'MathJax could not run: {e}') from e
    if result.returncode:
        raise ExamError('MathJax failed. Run npm ci in the repository; check the reported TeX.\n' + result.stderr[-5000:])
    return result.stdout.strip()

def render_formulae(exam, cache):
    keys = sorted({key for _,key in formulae(exam)})
    if not keys: return {}
    cache = Path(cache); cache.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(BRIDGE.read_bytes() + json.dumps(keys,ensure_ascii=False).encode()).hexdigest()
    target = cache / (digest + '.json')
    if not target.is_file():
        request = cache / (digest + '.input.json'); write_json(request, keys)
        run_node(request, target)
    svgs = read_json(target)
    if set(svgs) != set(keys): raise ExamError('Formula cache differs from input. Remove the job .cache and rebuild.')
    return {key: Formula(svg) for key,svg in svgs.items()}

class Formula:
    def __init__(self, svg):
        self.root = ET.fromstring(svg)
        x,y,w,h = map(float,self.root.attrib['viewBox'].split())
        self.width = w/1000; self.up = -y/1000; self.down = (y+h)/1000

    def draw(self, c):
        c.scale(.001,-.001)
        self._element(c,self.root)

    def _element(self,c,e):
        tag=e.tag.rsplit('}',1)[-1];c.saveState()
        transform=e.get('transform','')
        if transform and not re.fullmatch(r'\s*(?:(?:translate|scale|matrix)\s*\([^)]+\)\s*)+',transform):
            raise ExamError('Unsupported SVG transformation '+transform)
        for op,args in re.findall(r'(translate|scale|matrix)\s*\(([^)]+)\)',transform):
            a=[float(x) for x in re.split(r'[ ,]+',args.strip())]
            if op=='translate':c.translate(a[0],a[1] if len(a)>1 else 0)
            elif op=='scale':c.scale(a[0],a[1] if len(a)>1 else a[0])
            else:c.transform(*a)
        if tag=='path':
            s=SvgPath(e.attrib['d']);p=c.beginPath();i=0
            for op in s.operators:
                if op==0:p.moveTo(*s.points[i:i+2]);i+=2
                elif op==1:p.lineTo(*s.points[i:i+2]);i+=2
                elif op==2:p.curveTo(*s.points[i:i+6]);i+=6
                elif op==3:p.close()
                else:raise ExamError(f'Unknown SVG path command {op}')
            c.drawPath(p,stroke=0,fill=1,fillMode=1)
        elif tag=='rect':
            c.rect(float(e.get('x',0)),float(e.get('y',0)),float(e.get('width',0)),float(e.get('height',0)),stroke=0,fill=1)
        elif tag not in ('svg','g'):
            raise ExamError(f'Unsupported SVG element {tag}. Keep Korean prose outside $math$ and use supported TeX.')
        for child in e:self._element(c,child)
        c.restoreState()
