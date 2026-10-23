import copy
import math
import tempfile
import unittest
from pathlib import Path
from math_testpaper.model import ExamError, read_json, rich_parts, resolve_asset, validate_exam

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'examples/demo'

class ModelTests(unittest.TestCase):
    def setUp(self):self.exam=read_json(BASE/'exam.json')

    def test_demo_counts(self):
        self.assertEqual(validate_exam(self.exam,BASE),dict(questions=7,choices=12,total_marks=14))

    def test_pending_review_is_rejected(self):
        self.exam['questions'][0]['review']['status']='pending'
        with self.assertRaisesRegex(ExamError,'pending'):validate_exam(self.exam,BASE)

    def test_expected_count_must_match(self):
        self.exam['expected_question_count']=8
        with self.assertRaisesRegex(ExamError,'count'):validate_exam(self.exam,BASE)

    def test_expected_marks_must_match(self):
        self.exam['questions'][0]['score']=3
        with self.assertRaisesRegex(ExamError,'score'):validate_exam(self.exam,BASE)

    def test_duplicate_number_rejected(self):
        self.exam['questions'][1]['number']=1
        with self.assertRaisesRegex(ExamError,'unique'):validate_exam(self.exam,BASE)

    def test_nonfinite_score_rejected(self):
        self.exam['questions'][0]['score']=math.nan
        with self.assertRaisesRegex(ExamError,'score'):validate_exam(self.exam,BASE)

    def test_choice_type_cannot_lose_its_choices(self):
        self.exam['questions'][0]['choices']=[]
        with self.assertRaisesRegex(ExamError,'2-8'):validate_exam(self.exam,BASE)

    def test_nat_cannot_have_choices(self):
        self.exam['questions'][1]['choices']=['a','b']
        with self.assertRaisesRegex(ExamError,'non-choice'):validate_exam(self.exam,BASE)

    def test_choice_rounding_cannot_be_silently_omitted(self):
        self.exam['questions'][0]['rounding']='반올림 조건'
        with self.assertRaisesRegex(ExamError,'stem'):validate_exam(self.exam,BASE)

    def test_guide_metadata_is_a_list(self):
        self.exam['instructions']='a string is not a list'
        with self.assertRaisesRegex(ExamError,'list of strings'):validate_exam(self.exam,BASE)

    def test_unclosed_math_rejected(self):
        for s in ('before $x','$$x$','$$ $$'):
            with self.subTest(s=s), self.assertRaises(ExamError):list(rich_parts(s))

    def test_inline_display_and_literal_dollar(self):
        self.assertEqual(list(rich_parts(r'A $x$ B $$y$$ C \$5')),[('text','A '),('inline','x'),('text',' B '),('display','y'),('text',' C $5')])

    def test_asset_escape_rejected(self):
        with self.assertRaisesRegex(ExamError,'outside'):resolve_asset(BASE,'../../README.md')

    def test_absolute_asset_rejected(self):
        with self.assertRaisesRegex(ExamError,'outside'):resolve_asset(BASE,str((BASE/'parabola.pdf').resolve()))

    def test_invalid_figure_crop_rejected(self):
        self.exam['questions'][4]['figures'][0]['bbox']=[100,100,50,50]
        with self.assertRaisesRegex(ExamError,'bbox'):validate_exam(self.exam,BASE)

    def test_negative_source_page_rejected(self):
        self.exam['questions'][0]['source_pages']=[0]
        with self.assertRaisesRegex(ExamError,'source_pages'):validate_exam(self.exam,BASE)

    def test_source_hash_and_page_references_required(self):
        self.exam['source']={'path':'parabola.pdf','sha256':'0'*64}
        with self.assertRaisesRegex(ExamError,'hash'):validate_exam(self.exam,BASE)

if __name__=='__main__':unittest.main()
