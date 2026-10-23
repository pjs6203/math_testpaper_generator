from __future__ import annotations
from pathlib import Path
from pypdf import PdfReader
from .model import ExamError, read_json, sha256, write_json

def verify(directory,require_reviewed=False):
    directory=Path(directory);pdf=directory/'exam.pdf';report=read_json(directory/'validation.json');reader=PdfReader(pdf)
    if sha256(pdf)!=report['pdf_sha256']:raise ExamError('PDF hash differs from validation.json; rebuild')
    if len(reader.pages)!=report['pages']:raise ExamError('Page count differs from validation report')
    if sha256(directory/'exam.json')!=report['exam_snapshot_sha256']:raise ExamError('Exam snapshot changed; rebuild')
    if any(list(map(float,p.mediabox))!=[0,0,*report['page_size_pt']] for p in reader.pages):raise ExamError('PDF page dimensions changed')
    if len(report['layouts'])!=report['questions']:raise ExamError('Question placement count differs')
    seen=set()
    for i,q in enumerate(report['layouts']):
        placement=(q['page'],q['column'])
        if placement in seen or placement!=(i//2+1,i%2+1):raise ExamError('One-question-per-column contract failed')
        seen.add(placement)
    manifest_path=directory/'pages/manifest.json'
    if manifest_path.exists():
        manifest=read_json(manifest_path)
        if manifest['pdf_sha256']!=report['pdf_sha256']:raise ExamError('Page previews belong to an old PDF; render again')
        if any(not (directory/f'pages/page-{i:03d}.png').is_file() for i in range(1,len(reader.pages)+1)):raise ExamError('A page preview is missing')
    if require_reviewed:
        review=read_json(directory/'review.json')
        if review['pdf_sha256']!=report['pdf_sha256'] or sorted(review['reviewed_pages'])!=list(range(1,len(reader.pages)+1)):
            raise ExamError('Final visual review is missing or stale')
    return dict(passed=True,pages=len(reader.pages),questions=report['questions'],visual_review='complete' if require_reviewed else report.get('visual_review','pending'))

def record_review(directory,pages=None,*,all_pages=False,reviewer='AI',note=''):
    directory=Path(directory);verify(directory);report=read_json(directory/'validation.json')
    manifest=read_json(directory/'pages/manifest.json')
    if manifest['pdf_sha256']!=report['pdf_sha256']:raise ExamError('Render the final PDF before reviewing')
    selected=list(range(1,report['pages']+1)) if all_pages else (pages or [])
    if not selected or any(not 1<=i<=report['pages'] for i in selected):raise ExamError('Specify valid --pages or --all-pages after inspecting the PNGs')
    if not note.strip():raise ExamError('A review note describing what was inspected is required')
    path=directory/'review.json';prior=read_json(path) if path.exists() else {}
    old=prior.get('reviewed_pages',[]) if prior.get('pdf_sha256')==report['pdf_sha256'] else []
    data=dict(pdf_sha256=report['pdf_sha256'],reviewer=reviewer,reviewed_pages=sorted(set(old+selected)),note=note)
    write_json(path,data);report['visual_review']='complete' if len(data['reviewed_pages'])==report['pages'] else 'partial'
    write_json(directory/'validation.json',report)
    return data
