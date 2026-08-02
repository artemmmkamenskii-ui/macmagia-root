#!/usr/bin/env python3
"""Парсим все 6 docx, делаем один сводный CSV cluster,seed,phrase,frequency."""
import os
import re
import csv
import sys
import zipfile
from xml.etree import ElementTree as ET

BASE = '/Users/artemkamenskij/Desktop/сайты Макмагии/общий лендинг/сео/Ключи'
OUT = '/Users/artemkamenskij/Desktop/сайты Макмагии/общий лендинг/docs/seo/raw/wordstat-all-raw.csv'

# Сопоставление файл -> метка кластера
FILE_CLUSTER = {
    'Кластер A — психо-тесты.docx': 'A_psycho_tests',
    'Кластер B — эмоции : состояния.docx': 'B_emotions',
    'Кластер C — отношения.docx': 'C_relationships',
    'Кластер D — самопознание.docx': 'D_self_knowledge',
    'Кластер F - мак карты ключи .docx': 'F_mak_art_ai',
    'Психотерапия и практики.docx': 'G_therapy_practices',
}

NS = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
DASH_RE = re.compile(r'^-+$')
LINE_RE = re.compile(r'^(.+?)\s*(\d[\d\s]*)$')


def extract_paragraphs(docx_path):
    """Возвращает список параграфов: либо строка текста, либо None для пустых."""
    with zipfile.ZipFile(docx_path) as zf:
        xml_text = zf.read('word/document.xml').decode('utf-8')
    root = ET.fromstring(xml_text)
    out = []
    for p in root.iter(NS + 'p'):
        text = ''
        for r in p.iter(NS + 'r'):
            for t in r.iter(NS + 't'):
                text += t.text or ''
        out.append(text.strip())
    return out


def parse_docx(path, cluster_label, all_rows):
    paragraphs = extract_paragraphs(path)
    current_seed = None
    expecting_seed = True
    count = 0
    for raw in paragraphs:
        line = raw.strip()
        if not line:
            continue
        if DASH_RE.match(line):
            expecting_seed = True
            continue
        if expecting_seed:
            current_seed = line
            expecting_seed = False
            continue
        m = LINE_RE.match(line)
        if not m:
            continue
        phrase = m.group(1).strip()
        freq_str = m.group(2).replace(' ', '')
        try:
            freq = int(freq_str)
        except ValueError:
            continue
        if phrase and current_seed:
            all_rows.append({
                'cluster': cluster_label,
                'seed': current_seed,
                'phrase': phrase,
                'frequency': freq,
            })
            count += 1
    return count


all_rows = []
file_summary = []
for fname, cluster in FILE_CLUSTER.items():
    path = os.path.join(BASE, fname)
    if not os.path.exists(path):
        print(f'MISSING: {fname}', file=sys.stderr)
        continue
    n = parse_docx(path, cluster, all_rows)
    file_summary.append((fname, cluster, n))

with open(OUT, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['cluster', 'seed', 'phrase', 'frequency'])
    w.writeheader()
    w.writerows(all_rows)

print('\nFILE PARSE SUMMARY:', file=sys.stderr)
for fname, cluster, n in file_summary:
    print(f'  {cluster:<22}  {n:>6} rows  ({fname})', file=sys.stderr)
print(f'\nTOTAL_ROWS={len(all_rows)}', file=sys.stderr)
print(f'OUT={OUT}', file=sys.stderr)
