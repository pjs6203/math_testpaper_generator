from __future__ import annotations
import copy
import re
import shutil
from pathlib import Path
import pypdfium2 as pdfium
from pypdf import PdfReader, PdfWriter
from pypdf.generic import RectangleObject
from .model import ExamError, read_json, sha256, write_json

def render_pdf(pdf_path,directory,dpi=110):
    if not 36<=dpi<=400:raise ExamError('Render dpi must be between 36 and 400')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    # Only the renderer's own named PNG files are replaced.
    for old in directory.glob('page-*.png'):
        if re.fullmatch(r'page-\d+\.png',old.name):old.unlink()
    doc=pdfium.PdfDocument(str(pdf_path));count=len(doc)
    try:
        for i in range(count):
            page=doc[i];bitmap=page.render(scale=dpi/72)
            try:bitmap.to_pil().save(directory/f'page-{i+1:03d}.png')
            finally:bitmap.close();page.close()
    finally:doc.close()
    manifest=dict(pdf_sha256=sha256(pdf_path),pages=count,dpi=dpi)
    write_json(directory/'manifest.json',manifest)
    return manifest

def prepare(pdf_path,workdir,*,title=None,count=None,total=None,dpi=110):
    pdf_path=Path(pdf_path).resolve();workdir=Path(workdir).resolve()
    if not pdf_path.is_file():raise ExamError('Input PDF not found: '+str(pdf_path))
    if workdir.exists() and any(workdir.iterdir()):
        raise ExamError('Work directory is not empty. Continue the existing exam.json, or choose a new --workdir; do not overwrite an AI transcription.')
    workdir.mkdir(parents=True,exist_ok=True);source=workdir/'input.pdf';shutil.copy2(pdf_path,source)
    reader=PdfReader(source)
    if reader.is_encrypted and not reader.decrypt(''):raise ExamError('Input PDF is encrypted. Supply an unlocked copy.')
    pages=[];text=[];hints=[]
    for i,p in enumerate(reader.pages,1):
        s=p.extract_text(extraction_mode='layout') or ''
        pages.append(dict(page=i,media_box=list(map(float,p.mediabox)),rotation=int(p.get('/Rotate',0)),text_characters=len(s.strip())))
        text+=['\n--- SOURCE PAGE '+str(i)+' ---\n',s]
        for m in re.finditer(r'(?:^|\n)\s*(?:Q\.?\s*(\d{1,3})\b|\[(\d{1,3})\]|(\d{1,3})[.)])',s):
            hints.append(dict(number=int(next(v for v in m.groups() if v)),page=i))
    (workdir/'source.txt').write_text('\n'.join(text),encoding='utf8')
    write_json(workdir/'source.json',dict(original_filename=pdf_path.name,sha256=sha256(source),pages=pages,
               numbering_hints=hints,warning='Numbering hints may include instructions or omit scanned questions; an AI must count and inspect every page.'))
    render_pdf(source,workdir/'source_pages',dpi)
    questions=[dict(number=n,score=None,type='FREE',stem='',choices=[],source_pages=[],review={'status':'pending','notes':[]}) for n in range(1,(count or 0)+1)]
    exam=dict(schema_version=1,title=title or pdf_path.stem+' 한국어 편집본',subject='수 학',exam_code='수학',edition='한국어 편집본',
              language='ko-KR',duration_minutes=None,expected_question_count=count,expected_total_marks=total,
              source={'path':'input.pdf','sha256':sha256(source),'url':None},instructions=[],glossary=[],notes=[],questions=questions)
    write_json(workdir/'exam.json',exam)
    return dict(workdir=str(workdir),source_pages=len(pages),numbering_hints=len(hints),exam=str(workdir/'exam.json'))

def crop_figure(source,out,page_number,box):
    reader=PdfReader(source)
    if not 1<=page_number<=len(reader.pages):raise ExamError('Figure page is out of range')
    page=copy.copy(reader.pages[page_number-1])
    if page.get('/Rotate',0):page.transfer_rotation_to_content()
    media=list(map(float,page.mediabox));x0,y0,x1,y1=box
    if not (media[0]<=x0<x1<=media[2] and media[1]<=y0<y1<=media[3]):raise ExamError('Crop box is outside the normalized PDF page')
    page.cropbox=RectangleObject(box);page.mediabox=RectangleObject(box)
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True);writer=PdfWriter();writer.add_page(page);writer.write(out)
    return dict(path=str(out),page=1,bbox=box,coordinates='PDF points; origin at bottom left after page rotation normalization')
