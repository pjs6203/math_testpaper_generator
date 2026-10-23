"""Author an original vector diagram for the self-contained demo."""
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

root=Path(__file__).resolve().parents[1]
target=root/'examples/demo/parabola.pdf'
pdfmetrics.registerFont(TTFont('DiagramBody',str(root/'src/math_testpaper/assets/fonts/NanumMyeongjo-Regular.ttf')))
c=canvas.Canvas(str(target),pagesize=(280,190),pageCompression=1,initialFontName='DiagramBody')
c.setTitle('Original demonstration diagram: y=x^2')
c.setLineWidth(.8);c.line(35,25,255,25);c.line(35,25,35,170)
c.setFont('DiagramBody',12)
c.drawString(254,12,'x');c.drawString(21,172,'y');c.drawString(22,12,'O')
c.setFont('DiagramBody',11);c.drawString(229,12,'1');c.drawString(18,143,'1')
c.setDash(3,3);c.line(235,25,235,145);c.line(35,145,235,145);c.setDash()
p=c.beginPath();p.moveTo(35,25)
for n in range(1,101):
    x=n/100;p.lineTo(35+200*x,25+120*x*x)
c.setLineWidth(1.2);c.drawPath(p);c.showPage();c.save()
print(target)
