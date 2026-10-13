from pathlib import Path
import mistune
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent
md=(ROOT/'EXPECTED_OUTPUTS_PLAYBOOK_HE.md').read_text(encoding='utf-8')
markdown=mistune.create_markdown(plugins=['table'])
inner=markdown(md)
css='''
@page { size: A4; margin: 17mm 17mm 17mm 17mm; }
html,body{font-family:"Noto Sans Hebrew","Arial",sans-serif;font-size:10.25pt;line-height:1.58;color:#253349;direction:rtl;margin:0;}
body{background:white}h1,h2,h3{color:#3f4a5e;break-after:avoid;page-break-after:avoid;line-height:1.32;}
h1{font-size:21pt;border-bottom:3px solid #ff780b;padding-bottom:14px;margin:0 0 24px;}
h2{font-size:14.5pt;border-right:4px solid #ff780b;padding-right:10px;margin-top:24px;margin-bottom:9px;}
h3{font-size:12pt;margin:13px 0 6px;}
p{margin:7px 0 10px}strong{color:#263448}
table{border-collapse:collapse;width:100%;font-size:8.4pt;line-height:1.45;margin:10px 0 16px;table-layout:auto;}th{background:#3f4a5e;color:white;text-align:right;padding:7px 8px;}td{padding:6px 7px;border-bottom:1px solid #dfe5eb;vertical-align:top;overflow-wrap:anywhere;}tbody tr:nth-child(even){background:#f5f7fa}tr{break-inside:avoid;page-break-inside:avoid}thead{display:table-header-group}
ul,ol{padding-right:22px;margin:6px 0 12px;}li{margin-bottom:5px}code{direction:ltr;unicode-bidi:embed;font-size:8.6pt;background:#f0f2f5;border-radius:3px;padding:1px 3px;overflow-wrap:anywhere}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f5f7;padding:12px;font-size:9pt;}
blockquote{border-right:3px solid #ff780b;padding-right:13px;background:#fff9f2;}
.header{font-size:8pt;color:#687685;text-align:center;padding:8px 0;border-bottom:1px solid #e4e7ea;margin-bottom:17px;display:flex;justify-content:space-between;}
.footer{font-size:8pt;color:#687685;border-top:1px solid #e4e7ea;padding-top:7px;margin-top:17px}
@media print { .header{display:none} .footer{display:none} h2{break-after:avoid} }
'''
html='<!doctype html><html lang="he" dir="rtl"><head><meta charset="UTF-8"><style>'+css+'</style></head><body><div class="header"><span>MIZRAHI TOUCH × JEEN · QA GOLDEN SET</span><span>v1.1 · 12.10.2026</span></div><main>'+inner+'</main><div class="footer">מסמכים סינתטיים בלבד · Expected Output אינו תוצאת הרצת מודל.</div></body></html>'
(ROOT/'EXPECTED_OUTPUTS_PLAYBOOK_HE.html').write_text(html,encoding='utf-8')
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':1000,'height':1300},device_scale_factor=1)
 page.set_content(html,wait_until='load')
 page.pdf(path=str(ROOT/'EXPECTED_OUTPUTS_PLAYBOOK_HE.pdf'),format='A4',print_background=True,margin={'top':'0','bottom':'0','left':'0','right':'0'},prefer_css_page_size=True)
 browser.close()
import fitz
pdf=fitz.open(ROOT/'EXPECTED_OUTPUTS_PLAYBOOK_HE.pdf')
print('PLAYBOOK PDF PAGES',len(pdf),'SIZE_KB',round((ROOT/'EXPECTED_OUTPUTS_PLAYBOOK_HE.pdf').stat().st_size/1000))
# render first/last to small QA image
from PIL import Image,ImageDraw
imgs=[]
for idx in [0,len(pdf)//2,len(pdf)-1]:
 pix=pdf[idx].get_pixmap(matrix=fitz.Matrix(.85,.85)); im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples);imgs.append(im)
contact=Image.new('RGB',(sum(x.width for x in imgs)+48, max(x.height for x in imgs)+40),'#e5eaf0');offset=12
for im in imgs:contact.paste(im,(offset,15));offset+=im.width+12
contact.save(ROOT/'playbook_preview.png')
