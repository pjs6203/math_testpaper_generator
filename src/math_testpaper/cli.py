from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from . import __version__
from .fonts import register_fonts
from .layout import build_exam
from .mathsvg import run_node
from .model import ExamError, read_json, validate_exam
from .qa import record_review, verify
from .source import crop_figure, prepare, render_pdf

def parser():
    p=argparse.ArgumentParser(description='PDF understanding by an AI, deterministic math exam typesetting by this CLI.')
    p.add_argument('--version',action='version',version=__version__);sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor',help='Check bundled fonts, PDF renderer, and local MathJax')
    a=sub.add_parser('prepare',help='Copy and inspect a source PDF; render all pages; create a draft exam.json')
    a.add_argument('pdf',type=Path);a.add_argument('--workdir',type=Path,required=True);a.add_argument('--title');a.add_argument('--questions',type=int);a.add_argument('--total-marks',type=float);a.add_argument('--dpi',type=float,default=110)
    a=sub.add_parser('validate',help='Validate an AI-authored exam JSON before building')
    a.add_argument('exam',type=Path);a.add_argument('--allow-draft',action='store_true')
    a=sub.add_parser('build',help='Typeset the exam and render page PNGs')
    a.add_argument('exam',type=Path);a.add_argument('--out',type=Path,required=True);a.add_argument('--font-profile',choices=['auto','nanum','hy'],default='auto');a.add_argument('--fonts',type=Path);a.add_argument('--template',type=Path);a.add_argument('--no-render',action='store_true');a.add_argument('--dpi',type=float,default=110)
    a=sub.add_parser('render',help='Render an existing PDF without opening an application')
    a.add_argument('pdf',type=Path);a.add_argument('--out',type=Path,required=True);a.add_argument('--dpi',type=float,default=110)
    a=sub.add_parser('verify',help='Re-open the generated PDF and check its report')
    a.add_argument('directory',type=Path);a.add_argument('--require-reviewed',action='store_true')
    a=sub.add_parser('review',help='Record pages actually inspected by the calling AI or human')
    a.add_argument('directory',type=Path);g=a.add_mutually_exclusive_group(required=True);g.add_argument('--pages',nargs='+',type=int);g.add_argument('--all-pages',action='store_true');a.add_argument('--reviewer',default='AI');a.add_argument('--note',required=True)
    a=sub.add_parser('crop-figure',help='Copy a PDF figure crop as a vector PDF asset')
    a.add_argument('pdf',type=Path);a.add_argument('--page',type=int,required=True);a.add_argument('--box',nargs=4,type=float,required=True,metavar=('X0','Y0','X1','Y1'));a.add_argument('--out',type=Path,required=True)
    return p

def main(argv=None):
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf8')
    p=parser();a=p.parse_args(argv)
    try:
        if a.command=='doctor':
            _,fonts=register_fonts('nanum');result=dict(version=__version__,python=sys.version.split()[0],mathjax=run_node('--version'),fonts=fonts['profile'],pdf_renderer='pypdfium2',api_key_required=False)
        elif a.command=='prepare':
            if a.questions is not None and a.questions<1:raise ExamError('--questions must be positive')
            result=prepare(a.pdf,a.workdir,title=a.title,count=a.questions,total=a.total_marks,dpi=a.dpi)
        elif a.command=='validate':result=validate_exam(read_json(a.exam),a.exam.resolve().parent,allow_draft=a.allow_draft)
        elif a.command=='build':
            report=build_exam(a.exam,a.out,font_profile=a.font_profile,fonts=a.fonts,template=a.template)
            if not a.no_render:render_pdf(a.out/'exam.pdf',a.out/'pages',a.dpi)
            result={k:report[k] for k in ('pages','questions','choices','total_marks','visual_review')};result['pdf']=str((a.out/'exam.pdf').resolve())
        elif a.command=='render':result=render_pdf(a.pdf,a.out,a.dpi)
        elif a.command=='verify':result=verify(a.directory,a.require_reviewed)
        elif a.command=='review':result=record_review(a.directory,a.pages,all_pages=a.all_pages,reviewer=a.reviewer,note=a.note)
        elif a.command=='crop-figure':result=crop_figure(a.pdf,a.out,a.page,a.box)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (ExamError,OSError,KeyError,TypeError,ValueError) as e:
        print('ERROR: '+str(e),file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
