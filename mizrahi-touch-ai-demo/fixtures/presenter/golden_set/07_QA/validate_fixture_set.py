#!/usr/bin/env python3
"""Run in extracted Golden Set root: python3 07_QA/validate_fixture_set.py"""
import json,hashlib,csv,sys
from pathlib import Path
import fitz
root=Path(__file__).resolve().parents[1]
manifest=list(csv.DictReader((root/'MANIFEST.csv').open(encoding='utf-8-sig')))
errors=[];scan_cnt=0;total_pages=0
for r in manifest:
    path=root/r['path']
    if not path.exists():errors.append('MISSING '+r['path']);continue
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if digest!=r['sha256']:errors.append('HASH MISMATCH '+r['path'])
    d=fitz.open(path);total_pages+=len(d)
    if len(d)!=int(r['pages']):errors.append('PAGE COUNT '+r['path'])
    if r['input_mode']=='image_only':
        scan_cnt+=1
        if ''.join(p.get_text() for p in d).strip():errors.append('SCAN HAS PDF TEXT '+r['path'])
    elif len(''.join(p.get_text() for p in d))<100:errors.append('DIGITAL PDF NO TEXT '+r['path'])
    d.close()
gt=json.loads((root/'05_EXPECTED/document_ground_truth.json').read_text(encoding='utf-8'))
for path,metadata in gt['documents'].items():
    if not (root/path).exists():errors.append('MISSING TRUTH FILE '+path)
print('FILES',len(manifest),'PAGES',total_pages,'IMAGE_ONLY',scan_cnt,'GROUND_TRUTH',len(gt['documents']))
print('PASS' if not errors else 'FAIL '+str(errors))
sys.exit(bool(errors))
