from __future__ import annotations
import hashlib
import json
import math
import re
from pathlib import Path

class ExamError(ValueError):
    """Actionable input, layout, or verification error."""

def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (ValueError, OSError) as e:
        raise ExamError(f'Cannot read JSON {path}: {e}') from e

def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf8')

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def resolve_asset(base, name):
    if not isinstance(name, str) or not name:
        raise ExamError('Asset path must be a non-empty relative path')
    # Portable jobs cannot read outside their own directory.
    base = Path(base).resolve()
    candidate = (base / name).resolve()
    if Path(name).is_absolute() or not candidate.is_relative_to(base):
        raise ExamError(f'Asset is outside the exam directory: {name}')
    if not candidate.is_file():
        raise ExamError(f'Asset does not exist: {name}')
    return candidate

def rich_parts(text):
    """Yield (text|inline|display, content), rejecting unmatched delimiters."""
    if not isinstance(text, str):
        raise ExamError('Rich text must be a string')
    i = 0; literal = []
    while i < len(text):
        if text[i:i+2] == r'\$':
            literal.append('$'); i += 2; continue
        if text[i] != '$':
            literal.append(text[i]); i += 1; continue
        if literal:
            yield 'text', ''.join(literal); literal = []
        delimiter = '$$' if text[i:i+2] == '$$' else '$'
        start = i + len(delimiter); end = text.find(delimiter, start)
        if end < 0:
            raise ExamError(f'Unclosed {delimiter} math delimiter near {text[max(0,i-20):i+40]!r}')
        tex = text[start:end]
        if not tex.strip() or '$' in tex:
            raise ExamError('Empty or nested dollar math delimiters')
        yield ('display' if delimiter == '$$' else 'inline'), tex
        i = end + len(delimiter)
    if literal:
        yield 'text', ''.join(literal)

def question_texts(q):
    yield q['stem']
    yield from q.get('choices', [])
    if q.get('rounding'): yield q['rounding']
    for f in q.get('figures', []):
        if f.get('caption'): yield f['caption']

def formulae(exam):
    for q in exam['questions']:
        for text in question_texts(q):
            for kind, value in rich_parts(text):
                if kind != 'text':
                    yield q['number'], ('D:' if kind == 'display' else 'I:') + value

def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

def validate_exam(exam, base, *, allow_draft=False):
    if not isinstance(exam, dict) or exam.get('schema_version') != 1:
        raise ExamError('Expected an object with schema_version: 1')
    for field in ('title', 'subject', 'exam_code', 'edition'):
        if not isinstance(exam.get(field), str) or not exam[field].strip():
            raise ExamError(f'Missing non-empty metadata: {field}')
        if '\n' in exam[field] or '$' in exam[field]:
            raise ExamError(f'{field} must be plain single-line text')
    duration = exam.get('duration_minutes')
    if duration is not None and (not numeric(duration) or duration <= 0):
        raise ExamError('duration_minutes must be positive or null')
    questions = exam.get('questions')
    for field in ('instructions','glossary','notes'):
        if field in exam and (not isinstance(exam[field],list) or not all(isinstance(s,str) for s in exam[field])):
            raise ExamError(f'{field} must be a list of strings')
    if not isinstance(questions, list) or (not questions and not allow_draft):
        raise ExamError('questions must be a non-empty list')
    if exam.get('expected_question_count') is not None and exam['expected_question_count'] != len(questions):
        raise ExamError('Question count differs from expected_question_count')
    if exam.get('expected_question_count') is not None and (not isinstance(exam['expected_question_count'],int) or isinstance(exam['expected_question_count'],bool) or exam['expected_question_count']<1):
        raise ExamError('expected_question_count must be a positive integer')
    numbers = []; total = 0; all_scored = True
    source = exam.get('source') or {}
    source_pages = None
    if source.get('path'):
        if exam.get('expected_question_count') is None and not allow_draft:
            raise ExamError('Count the source questions and set expected_question_count before building')
        from pypdf import PdfReader
        path = resolve_asset(base, source['path'])
        if source.get('sha256') and sha256(path) != source['sha256']:
            raise ExamError('Source PDF hash changed; re-check the transcription')
        source_pages = len(PdfReader(path).pages)
    for q in questions:
        if not isinstance(q, dict): raise ExamError('Each question must be an object')
        n = q.get('number')
        if not isinstance(n, int) or isinstance(n, bool) or n < 1:
            raise ExamError('Question number must be a positive integer')
        numbers.append(n); prefix = f'Question {n}: '
        if q.get('type') not in ('MCQ', 'MSQ', 'NAT', 'FREE'):
            raise ExamError(prefix + 'type must be MCQ, MSQ, NAT, or FREE')
        choices = q.get('choices', [])
        if not isinstance(choices, list) or not all(isinstance(s, str) and s.strip() for s in choices):
            raise ExamError(prefix + 'choices must be a list of non-empty strings')
        if q['type'] in ('MCQ', 'MSQ') and not 2 <= len(choices) <= 8:
            raise ExamError(prefix + 'choice questions need 2-8 choices')
        if q['type'] in ('NAT', 'FREE') and choices:
            raise ExamError(prefix + 'non-choice questions cannot contain choices')
        if q['type'] in ('MCQ','MSQ') and q.get('rounding'):
            raise ExamError(prefix + 'put choice-question rounding instructions in stem so they are printed')
        if not isinstance(q.get('stem'), str) or (not q['stem'].strip() and not allow_draft):
            raise ExamError(prefix + 'stem is empty')
        if not allow_draft and q.get('review', {}).get('status') != 'verified':
            raise ExamError(prefix + 'source review is pending; compare with the original PDF first')
        pages = q.get('source_pages', [])
        if not isinstance(pages, list) or any(not isinstance(p, int) or isinstance(p, bool) or p < 1 or (source_pages and p > source_pages) for p in pages):
            raise ExamError(prefix + 'invalid 1-based source_pages')
        if source_pages and not pages and not allow_draft:
            raise ExamError(prefix + 'source_pages is required when a source PDF is present')
        score = q.get('score')
        if score is None: all_scored = False
        elif not numeric(score) or score < 0: raise ExamError(prefix + 'invalid score')
        else: total += score
        for text in question_texts(q):
            list(rich_parts(text))
        for figure in q.get('figures', []):
            path = resolve_asset(base, figure.get('path'))
            if path.suffix.lower() not in ('.pdf', '.png', '.jpg', '.jpeg'):
                raise ExamError(prefix + 'figures must be PDF, PNG, or JPEG')
            if figure.get('width') is not None and (not numeric(figure['width']) or figure['width'] <= 0):
                raise ExamError(prefix + 'figure width must be positive')
            if path.suffix.lower() == '.pdf':
                from pypdf import PdfReader
                reader = PdfReader(path); page = figure.get('page', 1)
                if not isinstance(page, int) or isinstance(page, bool) or not 1 <= page <= len(reader.pages):
                    raise ExamError(prefix + 'invalid figure PDF page')
                box = figure.get('bbox', list(map(float, reader.pages[page-1].cropbox)))
                if not isinstance(box, list) or len(box) != 4 or not all(numeric(v) for v in box) or box[2] <= box[0] or box[3] <= box[1]:
                    raise ExamError(prefix + 'invalid figure bbox [x0,y0,x1,y1]')
                media = list(map(float, reader.pages[page-1].mediabox))
                if box[0] < media[0] or box[1] < media[1] or box[2] > media[2] or box[3] > media[3]:
                    raise ExamError(prefix + 'figure bbox is outside source page')
                if reader.pages[page-1].get('/Rotate', 0):
                    raise ExamError(prefix + 'normalize rotated figure PDF with crop-figure first')
    if numbers != sorted(set(numbers)):
        raise ExamError('Question numbers must be unique and in ascending source order')
    expected = exam.get('expected_total_marks')
    if expected is not None and (not numeric(expected) or not all_scored or abs(total-expected) > 1e-6):
        raise ExamError('Total score differs from expected_total_marks, or a score is missing')
    return dict(questions=len(questions), choices=sum(len(q.get('choices', [])) for q in questions), total_marks=total if all_scored else None)
