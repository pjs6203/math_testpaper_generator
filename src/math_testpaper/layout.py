from __future__ import annotations
import copy
import math
import re
import tempfile
from collections import Counter
from pathlib import Path
from PIL import Image
from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import RectangleObject
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from .fonts import ASSETS, register_fonts
from .mathsvg import render_formulae
from .model import ExamError, formulae, read_json, resolve_asset, rich_parts, sha256, validate_exam, write_json

def load_template(path=None):
    t=read_json(path or ASSETS/'kice_a3.json')
    for key in ('page_width','page_height','text_width','body_size','math_size','minimum_math_size'):
        if not isinstance(t.get(key),(int,float)) or t[key]<=0:raise ExamError('Invalid template field '+key)
    if len(t['columns'])!=2 or t['columns'][0]+t['indent']+t['text_width']>t['divider'] or t['columns'][1]+t['indent']+t['text_width']>t['right']+.1:
        raise ExamError('Template columns overlap or exceed the right rule')
    if t['content_bottom']<=t['rule_bottom']:raise ExamError('Content bottom must be above the bottom rule')
    return t

class Composer:
    def __init__(self,c,fonts,formulae,template,base):
        self.c=c;self.fonts=fonts;self.formulae=formulae;self.t=template;self.base=base
        self.boxes=[];self.current=0;self.page=0;self.texts=[];self.math_draws=[];self.shrinks=[]
        self.forms={};self.pdf_figures=[]

    def text(self,s,x,y,role='body',size=None,record=True):
        size=size or self.t['body_size'];font=self.fonts[role];f=pdfmetrics.getFont(font)
        missing=[ch for ch in s if not ch.isspace() and ord(ch) not in f.face.charToGlyph]
        if missing:raise ExamError(f'Question {self.current}: missing glyphs {missing!r}. Choose another font or put mathematical symbols in $TeX$.')
        self.c.setFont(font,size);self.c.drawString(x,y,s)
        if record:self.texts.append(s)
        self.boxes.append(dict(question=self.current,page=self.page,x=x,y=y-size*.25,w=pdfmetrics.stringWidth(s,font,size),h=size*1.05,kind='text'))

    def center(self,s,cx,y,role='head',size=12):
        self.text(s,cx-pdfmetrics.stringWidth(s,self.fonts[role],size)/2,y,role,size)

    def fitted(self,s,cx,y,max_width,role='head',size=12):
        width=pdfmetrics.stringWidth(s,self.fonts[role],size)
        actual=min(size,size*max_width/max(width,.001))
        if actual<8:raise ExamError(f'Header is too long: {s!r}. Shorten the metadata.')
        self.center(s,cx,y,role,actual)

    def math(self,key,x,y,size):
        f=self.formulae[key]
        if key not in self.forms:
            name='Math'+str(len(self.forms));self.forms[key]=name
            self.c.beginForm(name,-.02,-f.down-.02,f.width+.02,f.up+.02)
            f.draw(self.c);self.c.endForm()
        self.c.saveState();self.c.translate(x,y);self.c.scale(size,size);self.c.doForm(self.forms[key]);self.c.restoreState()
        self.math_draws.append((self.current,key))
        self.boxes.append(dict(question=self.current,page=self.page,x=x,y=y-f.down*size,w=f.width*size,h=(f.up+f.down)*size,kind='math'))

    def tokens(self,s,width):
        ts=[];size=self.t['body_size'];body=self.fonts['body']
        for kind,value in rich_parts(s):
            if kind=='text':
                for part in re.findall(r'\n|[^\S\n]+|[A-Za-z0-9]+|.',value):
                    if part=='\n':ts.append(dict(kind='break'));continue
                    space=part.isspace();text=' ' if space else part
                    ts.append(dict(kind='space' if space else 'text',text=text,w=pdfmetrics.stringWidth(text,body,size),up=size*.8,down=size*.2))
            else:
                display=kind=='display';key=('D:' if display else 'I:')+value;f=self.formulae[key]
                ms=min(self.t['math_size'],width/max(f.width,.001))
                if ms<self.t['minimum_math_size']:
                    raise ExamError(f'Question {self.current}: formula too wide ({ms:.2f} pt required). Split it with aligned; preserve all terms. TeX: {value}')
                if ms<self.t['math_size']-.001:self.shrinks.append(dict(question=self.current,tex=value,size=round(ms,3)))
                if display:ts.append(dict(kind='break'))
                ts.append(dict(kind='math',key=key,w=f.width*ms,up=f.up*ms,down=f.down*ms,size=ms,display=display))
                if display:ts.append(dict(kind='break'))
        return ts

    def flow(self,s,x,top,width=None):
        width=width or self.t['text_width'];lines=[];line=[];used=0
        def flush():
            nonlocal line,used
            while line and line[-1]['kind']=='space':line.pop()
            if line:lines.append(line)
            line=[];used=0
        for token in self.tokens(s,width):
            if token['kind']=='break':flush();continue
            if token['kind']=='space' and not line:continue
            if token['w']>width+.01:raise ExamError(f'Question {self.current}: unbreakable word is too wide')
            if line and used+token['w']>width+.01:
                if token.get('text') in (',','.','?',':',';',')',']','}'):
                    moved=line.pop();flush();line=[moved];used=moved['w']
                else:flush()
                if token['kind']=='space':continue
            line.append(token);used+=token['w']
        flush();y=top;first=None
        for line in lines:
            up=max(self.t['body_size']*.8,max(v['up'] for v in line));down=max(self.t['body_size']*.2,max(v['down'] for v in line))
            display=any(v.get('display') for v in line)
            if display:y-=7
            baseline=y-up
            if first is None:first=baseline
            used=sum(v['w'] for v in line);cx=x+(width-used)/2 if display else x
            for v in line:
                if v['kind']=='text':self.text(v['text'],cx,baseline)
                elif v['kind']=='math':self.math(v['key'],cx,baseline,v['size'])
                cx+=v['w']
            y=baseline-down-(9.5 if display else self.t['line_gap'])
        return y,first

    def figure(self,figure,x,top,width):
        path=resolve_asset(self.base,figure['path']);scale_width=min(figure.get('width',width),width)
        if path.suffix.lower()=='.pdf':
            page=PdfReader(path).pages[figure.get('page',1)-1]
            box=figure.get('bbox',list(map(float,page.cropbox)));w=box[2]-box[0];h=box[3]-box[1]
        else:
            with Image.open(path) as im:w,h=im.size
        scale=scale_width/w;h*=scale;fx=x+(width-scale_width)/2;fy=top-h
        if path.suffix.lower()=='.pdf':
            self.pdf_figures.append(dict(path=str(path),page=figure.get('page',1),bbox=box,output_page=self.page,x=fx,y=fy,scale=scale))
        else:self.c.drawImage(str(path),fx,fy,width=scale_width,height=h,mask='auto')
        self.boxes.append(dict(question=self.current,page=self.page,x=fx,y=fy,w=scale_width,h=h,kind='figure'))
        y=fy-12
        if figure.get('caption'):y,_=self.flow(figure['caption'],x,y,width)
        return y

    def choice_label(self,index,x,baseline):
        label=chr(0x2460+index)
        if ord(label) in pdfmetrics.getFont(self.fonts['body']).face.charToGlyph:
            self.text(label,x,baseline)
        else:
            # Nanum does not include circled digits. Draw the circle as a vector
            # and keep its numeral as embedded text rather than use a tofu glyph.
            size=self.t['body_size'];cx=x+size*.48;cy=baseline+size*.32
            self.c.setLineWidth(.4);self.c.circle(cx,cy,size*.46,stroke=1,fill=0)
            digit=str(index+1);fs=size*.72
            self.text(digit,cx-pdfmetrics.stringWidth(digit,self.fonts['body'],fs)/2,cy-fs*.34,size=fs)

    def question(self,q,x,top):
        self.current=q['number'];start=len(self.boxes);t=self.t
        typ={'MCQ':'단일정답형','MSQ':'복수정답형','NAT':'수치답형','FREE':'서답형'}[q['type']]
        score=f'  [{q["score"]:g}점]' if q.get('score') is not None else ''
        self.text(str(q['number'])+'.',x,top-10.9,'head',13.57)
        self.text(typ+score,x+t['indent'],top-10.9,size=10)
        y,_=self.flow(q['stem'],x+t['indent'],top-36)
        for figure in q.get('figures',[]):
            y=self.figure(figure,x+t['indent'],y-8,t['text_width'])
        if q.get('choices'):
            y-=12
            for index,choice in enumerate(q['choices']):
                ny,first=self.flow(choice,x+t['indent']+20,y,t['text_width']-20)
                self.choice_label(index,x+t['indent'],first);y=ny-10
        else:
            if q.get('rounding'):y,_=self.flow(q['rounding'],x+t['indent'],y-4)
            if q['type']=='NAT':
                y-=22;self.text('답:',x+t['indent'],y)
                self.c.setLineWidth(.36);self.c.line(x+t['indent']+24,y-3,x+t['indent']+154,y-3);y-=10
        for box in self.boxes[start:]:
            if box['x']<x-.1 or box['x']+box['w']>x+t['indent']+t['text_width']+.1:
                raise ExamError(f'Question {q["number"]}: content crosses a column boundary')
            if box['y']<t['content_bottom'] or box['y']+box['h']>top+1:
                raise ExamError(f'Question {q["number"]}: content exceeds the available column height. Preserve the problem; adjust layout explicitly.')
        if y<t['content_bottom']:raise ExamError(f'Question {q["number"]} exceeds the column height')
        self.current=0
        return y

    def decorate(self,exam,pn,total):
        self.page=pn;t=self.t;c=self.c;center=(t['left']+t['right'])/2
        if pn==1:
            self.fitted(exam['title'],center,1094.639,t['right']-t['left'],'head',20)
            heading='수    학' if exam['subject'].replace(' ','')=='수학' else exam['subject']
            self.fitted(heading,center,1039.619,t['right']-t['left'],'title',40)
            self.text('수험 번호 (                )    성명 (              )',417,995.519,'head',16)
            c.setLineWidth(.36)
            for yy in (969.659,932.999):c.line(t['left'],yy,t['right'],yy)
            edges=[t['left']+(t['right']-t['left'])*i/4 for i in range(5)]
            for xx in edges:c.line(xx,932.999,xx,969.659)
            marks=sum(q.get('score') or 0 for q in exam['questions']);all_scored=all(q.get('score') is not None for q in exam['questions'])
            stats=f'{len(exam["questions"])}문항'+(f' {marks:g}점' if all_scored else '')
            duration=f'시험 시간 {exam["duration_minutes"]:g}분' if exam.get('duration_minutes') else '수학 문제지'
            for i,label in enumerate([exam['exam_code'],exam.get('edition','한국어 편집본'),stats,duration]):
                self.fitted(label,(edges[i]+edges[i+1])/2,946.439,(edges[i+1]-edges[i])-12,'body',13)
            top=t['first_rule_top']
        else:
            self.fitted(f'{exam["subject"]} [{exam["exam_code"]}]',center,1088,t['right']-t['left'],'head',12)
            top=t['rule_top']
        c.setLineWidth(.54)
        for x0,y0,x1,y1 in [(t['left'],top,t['right'],top),(t['left'],t['rule_bottom'],t['right'],t['rule_bottom']),(t['divider'],t['rule_bottom'],t['divider'],top)]:c.line(x0,y0,x1,y1)
        self.fitted(f'{exam["subject"]} [{exam["exam_code"]}] ({total}면 중 {pn}면)',center,76.7391,t['right']-t['left'],'head',11)
        return t['first_question_top'] if pn==1 else t['question_top']

def merge_figures(source,dest,figures):
    writer=PdfWriter();writer.clone_document_from_reader(PdfReader(source));readers={}
    for f in figures:
        if f['path'] not in readers:readers[f['path']]=PdfReader(f['path'])
        page=copy.copy(readers[f['path']].pages[f['page']-1]);page.cropbox=RectangleObject(f['bbox'])
        x0,y0,_,_=f['bbox'];transform=Transformation().translate(-x0,-y0).scale(f['scale']).translate(f['x'],f['y'])
        writer.pages[f['output_page']-1].merge_transformed_page(page,transform,over=True,expand=False)
    writer.write(dest)

def build_exam(exam_path,out,*,font_profile='auto',fonts=None,template=None):
    exam_path=Path(exam_path).resolve();base=exam_path.parent;exam=read_json(exam_path)
    counts=validate_exam(exam,base);t=load_template(template);names,font_info=register_fonts(font_profile,fonts)
    maths=render_formulae(exam,base/'.cache');out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    pdf=out/'exam.pdf';total=math.ceil(len(exam['questions'])/2);layouts=[]
    with tempfile.TemporaryDirectory(prefix='exam-',dir=out) as temporary:
        plain=Path(temporary)/'body.pdf'
        c=canvas.Canvas(str(plain),pagesize=(t['page_width'],t['page_height']),pageCompression=1,initialFontName=names['body'],lang=exam.get('language','ko-KR'))
        c.setTitle(exam['title']);c.setCreator('math_testpaper_generator 0.1.0')
        comp=Composer(c,names,maths,t,base)
        for pi in range(total):
            top=comp.decorate(exam,pi+1,total)
            for col,q in enumerate(exam['questions'][pi*2:pi*2+2]):
                c.bookmarkPage(f'q{q["number"]}');c.addOutlineEntry(f'{q["number"]}번 - {q["type"]}',f'q{q["number"]}',0)
                bottom=comp.question(q,t['columns'][col],top)
                layouts.append(dict(number=q['number'],page=pi+1,column=col+1,top=top,bottom=round(bottom,3),type=q['type'],score=q.get('score')))
            c.showPage()
        c.save()
        plain_reader=PdfReader(plain)
        actual=Counter(re.sub(r'\s','',''.join(p.extract_text() or '' for p in plain_reader.pages)))
        expected=Counter(re.sub(r'\s','',''.join(comp.texts)))
        if actual!=expected:raise ExamError('Written PDF text encoding did not round-trip')
        if comp.pdf_figures:merge_figures(plain,pdf,comp.pdf_figures)
        else:pdf.write_bytes(plain.read_bytes())
    reader=PdfReader(pdf)
    if len(reader.pages)!=total:raise ExamError('Written page count differs from layout')
    if any(list(map(float,p.mediabox))!=[0,0,t['page_width'],t['page_height']] for p in reader.pages):raise ExamError('Written page geometry differs from template')
    if Counter(formulae(exam))!=Counter(comp.math_draws):raise ExamError('Formula missing or duplicated')
    # PDF figure text is additional to the generated text, so inspect the plain
    # text layer before merging figure assets, not a counter of the final PDF.
    font_objects={str(f.get_object().get('/BaseFont')):f.get_object() for p in reader.pages for f in p['/Resources'].get('/Font',{}).values()}
    def embedded(font):
        if font.get('/Subtype')=='/Type3':return True
        if font.get('/Subtype')=='/Type0':font=font['/DescendantFonts'][0].get_object()
        descriptor=font['/FontDescriptor'] if '/FontDescriptor' in font else {}
        return any(k in descriptor for k in ('/FontFile','/FontFile2','/FontFile3'))
    missing_fonts=[n for n,f in font_objects.items() if not embedded(f)]
    if missing_fonts and not comp.pdf_figures:raise ExamError('Text fonts are not embedded: '+str(missing_fonts))
    report=dict(schema_version=1,pdf_sha256=sha256(pdf),exam_sha256=sha256(exam_path),pages=total,page_size_pt=[t['page_width'],t['page_height']],**counts,
                question_types=dict(Counter(q['type'] for q in exam['questions'])),formula_instances=len(comp.math_draws),formulae_preserved=True,
                generated_text_roundtrip=True,font_info=font_info,unembedded_figure_fonts=missing_fonts,
                math_shrinks=comp.shrinks,layouts=layouts,one_question_per_column=True,no_application_automation=True,
                visual_review='pending',source_review='verified',limitations=['KICE-style geometry, not pixel-identical official KICE output.','Equations are vector paths, not a searchable formula text layer.'])
    write_json(out/'exam.json',exam)
    report['exam_snapshot_sha256']=sha256(out/'exam.json')
    write_json(out/'validation.json',report);write_json(out/'layout.json',comp.boxes)
    lines=['# '+exam['title'],'','원본 문항과 대조한 비공식 편집본입니다.','']
    if exam.get('source',{}).get('url'):lines+=['원문: '+exam['source']['url'],'']
    for heading,key in [('시험 안내','instructions'),('공통 기호','glossary'),('편집 기록','notes')]:
        if exam.get(key):lines+=['## '+heading,'']+['- '+s for s in exam[key]]+['']
    lines+=['## 선택지 대응','','원문의 선택지 순서를 유지하며 출력 라벨은 ①, ②, …입니다. 원문 라벨은 1번부터 순서대로 대응합니다.','',
            '## 조판','','A3 2단, 각 단에 한 문제. 홀수 개 문항의 마지막 오른쪽 단은 비워 둡니다.','',
            '본문 글꼴 프로필: '+font_info['profile']+'. 수식: MathJax TeX 벡터. 평가원 공식 서체와 차이가 있습니다.','',
            '프로그램 검사는 번역·수식 전사의 의미적 정확성을 보증하지 않습니다. source_pages와 review를 원문과 대조하고 최종 PNG를 확인해야 합니다.','']
    (out/'notes.md').write_text('\n'.join(lines),encoding='utf8')
    return report
