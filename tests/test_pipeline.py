import copy
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from pypdf import PdfReader
from math_testpaper.layout import build_exam
from math_testpaper.model import ExamError, read_json, write_json
from math_testpaper.qa import record_review, verify
from math_testpaper.source import crop_figure, prepare, render_pdf

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'examples/demo'

class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        scratch=(ROOT/'jobs').resolve();scratch.mkdir(exist_ok=True)
        cls.tmp=tempfile.TemporaryDirectory(dir=scratch);cls.root=Path(cls.tmp.name).resolve()
        assert cls.root.is_relative_to(scratch)
        cls.out=cls.root/'demo'
        cls.report=build_exam(BASE/'exam.json',cls.out,font_profile='nanum')

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def one_question(self,stem='테스트 문항',**kwargs):
        data=read_json(BASE/'exam.json');data['questions']=[copy.deepcopy(data['questions'][6])]
        data['questions'][0].update(number=1,stem=stem,**kwargs)
        data['expected_question_count']=1;data['expected_total_marks']=2
        target=self.root/self._testMethodName/'exam.json';write_json(target,data)
        return target

    def test_demo_has_four_a3_pages_and_odd_empty_slot(self):
        self.assertEqual(self.report['pages'],4)
        self.assertEqual([(p['page'],p['column']) for p in self.report['layouts']],[(1,1),(1,2),(2,1),(2,2),(3,1),(3,2),(4,1)])
        for page in PdfReader(self.out/'exam.pdf').pages:self.assertEqual(list(map(float,page.mediabox)),[0,0,842,1191])

    def test_formulae_and_generated_text_survive(self):
        self.assertTrue(self.report['formulae_preserved'])
        self.assertTrue(self.report['generated_text_roundtrip'])
        self.assertGreater(self.report['formula_instances'],20)

    def test_diagram_is_vector_and_fonts_embedded(self):
        self.assertEqual(self.report['unembedded_figure_fonts'],[])
        for page in PdfReader(self.out/'exam.pdf').pages:
            self.assertFalse(any(o.get_object().get('/Subtype')=='/Image' for o in page['/Resources'].get('/XObject',{}).values()))

    def test_validation_can_be_reopened(self):self.assertTrue(verify(self.out)['passed'])

    def test_missing_visual_review_rejected(self):
        with self.assertRaises(ExamError):verify(self.out,True)

    def test_review_is_bound_to_the_final_pdf_hash(self):
        separate=self.root/'review';build_exam(BASE/'exam.json',separate,font_profile='nanum');render_pdf(separate/'exam.pdf',separate/'pages',36)
        record_review(separate,all_pages=True,reviewer='unit-test',note='Synthetic test of the recording API; not a claim of human visual inspection.')
        self.assertTrue(verify(separate,True)['passed'])
        with (separate/'exam.pdf').open('ab') as f:f.write(b'\n%changed')
        with self.assertRaisesRegex(ExamError,'hash'):verify(separate,True)

    def test_source_prepare_creates_every_page_and_refuses_overwrite(self):
        job=self.root/'한국어 source job';result=prepare(self.out/'exam.pdf',job,count=7,total=14,dpi=36)
        self.assertEqual(result['source_pages'],4)
        self.assertEqual(len(list((job/'source_pages').glob('page-*.png'))),4)
        self.assertEqual(read_json(job/'exam.json')['questions'][0]['review']['status'],'pending')
        with self.assertRaisesRegex(ExamError,'not empty'):prepare(self.out/'exam.pdf',job)

    def test_bad_tex_is_an_error(self):
        path=self.one_question(r'잘못된 수식 $\definitelyNotACommand{x}$')
        with self.assertRaisesRegex(ExamError,'MathJax failed'):build_exam(path,path.parent/'out',font_profile='nanum')

    def test_missing_glyph_is_an_error(self):
        path=self.one_question('없는 글자 '+chr(0x10ffff))
        with self.assertRaisesRegex(ExamError,'missing glyph'):build_exam(path,path.parent/'out',font_profile='nanum')

    def test_oversize_formula_is_not_silently_squeezed(self):
        path=self.one_question('$'+'+'.join(['x']*200)+'$')
        with self.assertRaisesRegex(ExamError,'too wide'):build_exam(path,path.parent/'out',font_profile='nanum')

    def test_oversize_question_is_not_dropped(self):
        path=self.one_question('긴 문항입니다. '*3000)
        with self.assertRaisesRegex(ExamError,'height'):build_exam(path,path.parent/'out',font_profile='nanum')

    def test_pdf_crop_keeps_a_vector_asset(self):
        target=self.root/'crop.pdf';crop_figure(BASE/'parabola.pdf',target,1,[35,25,235,145])
        self.assertEqual(list(map(float,PdfReader(target).pages[0].mediabox)),[35,25,235,145])

    def test_raster_figure_is_supported(self):
        path=self.one_question('래스터 그림',figures=[{'path':'tiny.png','width':100}])
        Image.new('RGB',(40,20),'black').save(path.parent/'tiny.png')
        report=build_exam(path,path.parent/'out',font_profile='nanum')
        page=PdfReader(path.parent/'out/exam.pdf').pages[0]
        self.assertEqual(report['pages'],1)
        self.assertTrue(any(o.get_object().get('/Subtype')=='/Image' for o in page['/Resources']['/XObject'].values()))

if __name__=='__main__':unittest.main()
