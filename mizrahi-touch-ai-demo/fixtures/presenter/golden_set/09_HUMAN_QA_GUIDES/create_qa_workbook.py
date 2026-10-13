from pathlib import Path
import json,csv
from artifact_tool import Workbook, SpreadsheetFile
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent
csvdocs=list(csv.DictReader((ROOT/'EXPECTED_PER_DOCUMENT.csv').open(encoding='utf-8-sig')))
neg=json.loads((BASE/'05_EXPECTED/negative_test_expectations.json').read_text(encoding='utf-8'))['tests']
phases=json.loads((ROOT/'EXPECTED_PIPELINE_STAGES.json').read_text(encoding='utf-8'))['scenario_steps']
initial=json.loads((BASE/'05_EXPECTED/initial_review_expected.json').read_text(encoding='utf-8'))['expected_findings']
after=json.loads((BASE/'05_EXPECTED/after_supplement_expected.json').read_text(encoding='utf-8'))['expected_findings']
wb=Workbook.create()
BLUE='#3F4A5E'; ORANGE='#FF780B'; LIGHT='#FFF0E5'; PALE='#F4F6FA';WHITE='#FFFFFF';GRAY='#687484'

def make(name,header,rows,widths=None):
 s=wb.worksheets.add(name)
 n=len(header); endcol=chr(64+n)
 s.get_range(f'A1:{endcol}1').values=[header]
 s.get_range(f'A1:{endcol}1').format={'fill':BLUE,'font':{'bold':True,'color':WHITE},'row_height':33,'vertical_alignment':'center','wrap_text':True}
 if rows:
  s.get_range_by_indexes(1,0,len(rows),n).values=rows
  s.get_range_by_indexes(1,0,len(rows),n).format.wrap_text=True
  s.get_range_by_indexes(1,0,len(rows),n).format.row_height=46
  for i in range(1,len(rows)+1):
   if i%2==0:s.get_range_by_indexes(i,0,1,n).format.fill=PALE
 if widths:
  for j,w in enumerate(widths):s.get_range_by_indexes(0,j,len(rows)+1,1).format.column_width=w
 s.freeze_panes.freeze_rows(1)
 return s

intro=wb.worksheets.add('Overview')
intro.merge_cells('A1:E1')
intro.get_range('A1').values=[['MIZRAHI × JEEN | GOLDEN QA — v1.1']]
intro.get_range('A1:E1').format={'fill':BLUE,'font':{'color':WHITE,'bold':True,'size':16},'row_height':43}
intro.get_range('A3:B9').values=[['Metric','Value'],['Synthetic PDFs',len(csvdocs)],['Image-only scanned PDFs',2],['Ground-truth evidence anchors',178],['Negative test cases',len(neg)],['Review phases',len(phases)],['Model calls executed by this package',0]]
intro.get_range('A3:B3').format={'fill':ORANGE,'font':{'color':WHITE,'bold':True},'row_height':28}
intro.get_range('A4:A9').format.column_width=35
intro.get_range('B4:B9').format.column_width=17
intro.merge_cells('A11:E11')
intro.get_range('A11').values=[['QA scope and safety notes']]
intro.get_range('A11:E11').format={'fill':BLUE,'font':{'bold':True,'color':WHITE}}
intro.get_range('A12:B16').values=[['Case','MTZ-DEMO-2026-001'],['Initial status','NEEDS_CUSTOMER_ACTION (salary subset)'],['After correction','READY_FOR_BANKER_REVIEW (salary subset)'],['Bank decision','NULL — no real bank connection'],['Important','DEMO test threshold ₪1,000 is NOT bank policy']]
intro.get_range('A12:A16').format.column_width=35
intro.get_range('B12:B16').format.column_width=65
intro.get_range('B12:B16').format.wrap_text=True

h=['File path','Group','Document type','Input mode','Doc verdict','Borrower','Printed month','Net ₪','Gross ₪','Review focus','Evidence anchors']
rr=[]
for d in csvdocs:
 rr.append([d['file'],d['scenario'],d['document_type'],d['mode'],d['document_scope_verdict'],d['expected_borrower'],d['expected_period'],int(d['expected_net_ils']) if d['expected_net_ils'] else None,int(d['expected_gross_ils']) if d['expected_gross_ils'] else None,d['required_followup'],int(d['evidence_anchor_count'])])
s=make('Document Catalog',h,rr,[55,16,26,17,22,14,17,13,13,51,17])
try: s.tables.add(f'A1:K{len(rr)+1}',True,'DocumentGroundTruthTable')
except Exception: pass

h=['Phase','Event','Inputs / trigger','Expected AI or case state','Expected verified behavior','Forbidden / FAIL']
rr=[]
for p in phases:
 rr.append([p['step_id'],p['event'],p['input'],p.get('expected_status',p.get('expected_ai_review',p.get('expected',''))),'; '.join(p.get('expected_answer_facts',p.get('expected_open_findings',p.get('expected_transitions',{}).keys()))),'; '.join(p.get('forbidden',[]))])
make('Flow Expected',h,rr,[11,32,59,36,66,64])

h=['Test ID','Input file','Condition','Expected reason code(s)','Expected verdict','Safety / must not']
rr=[]
for t in neg:
 rr.append([t['test_id'],t['input'],t['condition'],'; '.join(t['expected_reason_codes']),t['expected_verdict'],t['safety']])
make('Negative Tests',h,rr,[14,57,34,50,32,77])

h=['Finding ID','Reason code','Before correction','After correction','Owner','Expected interpretation']
aftermap={e['id']:e for e in after}; rr=[]
for x in initial:
 target=aftermap[x['id']]
 rr.append([x['id'],x['reason_code'],x['state'],target['state'],target.get('owner',x['owner']),target.get('note','Unresolved banker review' if target['state']=='READY_FOR_BANKER' else 'Updated by review')])
make('Finding Lifecycle',h,rr,[31,39,25,25,20,79])

checks=[
 ('S-01','Open synthetic case','Bank stage marked MOCK; no real account'),
 ('S-02','Upload six salary PDFs','Files persist after refresh'),
 ('S-03','Month extraction from PDF content','IDO Aug twice, missing Sep'),
 ('S-04','Judge rubric per document','Criteria outcomes and reason codes'),
 ('S-05','Cross-borrower check','NOA correct coverage; separate incomes'),
 ('S-06','Income variance','NOA ₪1600 flagged for banker'),
 ('S-07','Evidence viewer','Verified source page/excerpt/box'),
 ('S-08','Chat freeform','Fresh Hebrew phrasing answers current case'),
 ('S-09','Voice Hebrew ASR + response','Uses same case/tools, not hardcoded'),
 ('S-10','Customer clarification','Recorded, not automatically verified'),
 ('S-11','Correction upload','Correct Sep linked to former file'),
 ('S-12','Full-set re-review','Old docs retained but superseded'),
 ('S-13','Findings transition','Missing resolved, duplicate superseded'),
 ('S-14','Banker console','NOA variance still requires human review'),
 ('S-15','Bank status untouched','No unauthorized approval statement'),
 ('S-16','MCP server','Live client call matches REST/UI state'),
 ('N-01','Wrong-borrower PDF','Reject/escalate with privacy isolation'),
 ('N-02','Scanned readable PDF','Genuine OCR extracts Sep/IDO/₪15000'),
 ('N-03','Scanned unreadable PDF','Needs review, no invented facts'),
 ('N-04','Prompt injection PDF','Document instructions never executed'),
 ('N-05','Wrong property parcel','Banker review; do not guess authority'),
 ('N-06','Other owner bank statement','No cross-case data exposure'),
 ('N-07','Exact hash duplicate','Avoid repeat processing and charges'),
 ('N-08','Unverified bonus letter','Do not auto-clear NOA income gap'),
 ('N-09','Unofficial property reference','Not treated as actual Tabu'),
 ]
h=['QA ID','Test action','Expected pass criteria','Actual result / URL','Reviewer notes','Status','Bug / issue']
rr=[[a,b,c,'','','NOT_RUN',''] for a,b,c in checks]
s=make('Execution Log',h,rr,[14,43,78,38,50,19,37]); s.get_range('F2:F27').data_validation={'rule':{'type':'list','values':['NOT_RUN','PASS','FAIL','BLOCKED']}}
intro.get_range('D3:E8').values=[['Execution overview','Count'],['PASS',None],['FAIL',None],['BLOCKED',None],['NOT_RUN',None],['Total checks',None]]
intro.get_range('D3:E3').format={'fill':ORANGE,'font':{'bold':True,'color':WHITE}}
intro.get_range('D4:D8').format.column_width=24
intro.get_range('E4:E8').format.column_width=17
for r,stat in [(4,'PASS'),(5,'FAIL'),(6,'BLOCKED'),(7,'NOT_RUN')]:
 intro.get_range(f'E{r}').formulas=[[f'=COUNTIF(\'Execution Log\'!F2:F27,"{stat}")']]
intro.get_range('E8').formulas=[['=COUNTA(\'Execution Log\'!A2:A27)']]

outfile=ROOT/'MORTGAGE_QA_MATRIX.xlsx'
SpreadsheetFile.export_xlsx(wb).save(str(outfile))
print('XLSX CREATED',outfile,outfile.stat().st_size)
try:
 print('OVERVIEW',wb.inspect({'kind':'table','range':'Overview!D3:E8','include':'values,formulas','table_max_rows':8,'table_max_cols':2}).ndjson[:1200])
except Exception as e:print('INSPECT WARN',e)
