from __future__ import annotations

import csv
import json
import math
import os
import posixpath
import re
import sqlite3
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

XLSX = Path('/mnt/data/current_task/Ежедневная сводка по работе машин АО Развитие Красноярск 2026.xlsx')
PROJECT = Path('/mnt/data/current_task/work')
OUTROOT = Path('/mnt/data/current_task/migration_output_v2')
CUSTOMER = 'АО «Развитие» ОГОК Komatsu'
CUSTOMER_DIR = OUTROOT / CUSTOMER
DB_PATH = CUSTOMER_DIR / 'journaltoir.db'
AUDIT_DIR = OUTROOT / 'audit_csv'

GRAPH_START = date(2022, 9, 1)
GRAPH_END = date(2026, 9, 18)
KOMATSU_BUILTIN_ID = -1001
NOW_STR = datetime.now().isoformat(sep=' ', timespec='seconds')

NS = {'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
CELL_RE = re.compile(r'([A-Z]+)(\d+)')
CYR_TO_LAT = str.maketrans({
    'А':'A','В':'B','Е':'E','К':'K','М':'M','Н':'H','О':'O','Р':'P','С':'C','Т':'T','Х':'X',
    'а':'A','в':'B','е':'E','к':'K','м':'M','н':'H','о':'O','р':'P','с':'C','т':'T','х':'X',
})

CAT_MAP = {
    1:'Работы заказчика',
    2:'ТО',
    3:'Мониторинг состояния',
    4:'Аварийный ремонт',
    5:'Плановый ремонт',
    6:'Модернизация',
    7:'Будущие работы',
}
FILL_TYPE = {
    8:'Работы заказчика', 32:'Работы заказчика',
    3:'ТО', 10:'ТО',
    2:'Мониторинг состояния',
    7:'Аварийный ремонт', 16:'Аварийный ремонт', 29:'Аварийный ремонт',
    30:'Аварийный ремонт', 31:'Аварийный ремонт',
    9:'Плановый ремонт', 18:'Плановый ремонт',
    5:'Модернизация',
    11:'Будущие работы',
}
UNAVAILABLE = {'Аварийный ремонт','Плановый ремонт','Модернизация','Простой','ТО'}


def col_to_num(col: str) -> int:
    n=0
    for ch in col:
        n=n*26 + ord(ch)-64
    return n

def num_to_col(n: int) -> str:
    s=''
    while n:
        n,r=divmod(n-1,26)
        s=chr(65+r)+s
    return s

def cell_parts(ref: str):
    m=CELL_RE.fullmatch(ref)
    return col_to_num(m.group(1)), int(m.group(2))

def norm_model(s):
    s=str(s or '').strip().translate(CYR_TO_LAT).upper()
    s=re.sub(r'\s+','',s).replace('_','-')
    aliases={
        'D375-5':'D375A-5','D375A-5':'D375A-5',
        'D375-6':'D375A-6','D375A-6':'D375A-6',
        'GD825-2':'GD825A-2','GD825A-2':'GD825A-2',
        'WA470-6':'WA470-6A','WA470-6A':'WA470-6A',
    }
    return aliases.get(s,s)

def norm_garage(s):
    s=str(s or '').strip().upper().translate(CYR_TO_LAT)
    s=re.sub(r'\.0$','',s)
    s=re.sub(r'[\s"«»]+','',s)
    return s

def norm_serial(s):
    s=str(s or '').strip().upper().translate(CYR_TO_LAT)
    s=re.sub(r'\.0$','',s)
    s=re.sub(r'[\s\-]+','',s)
    if re.fullmatch(r'A\d{4,}',s):
        s=s[1:]
    return s

def parse_excel_date(v):
    if v in (None,''):
        return None
    if isinstance(v,(int,float)):
        try:
            return (datetime(1899,12,30)+timedelta(days=float(v))).date()
        except Exception:
            return None
    s=str(v).strip()
    for fmt in ('%d.%m.%Y','%d.%m.%y','%Y-%m-%d','%d/%m/%Y','%d-%m-%Y'):
        try:
            return datetime.strptime(s,fmt).date()
        except Exception:
            pass
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        return None

def clean_comment(s):
    s=str(s or '').replace('\r\n','\n').replace('\r','\n')
    s=re.sub(r'^\s*Автор:\s*\n?', '', s, flags=re.I)
    return s.strip()

# В заметках ежедневного графика исполнители часто записаны отдельной
# строкой/блоком после текста работ: «...\n\nБеляев, Андреев». При импорте
# переносим их в отдельное поле executors, а пустые строки из описания убираем.
_SURNAME_RE = re.compile(
    r'.*(?:ов|ев|ёв|ин|ын|ский|цкий|енко|ук|юк|ич|ко|ец|цев|дзе|ян|ой|ий|ых|их|ович|евич)$',
    re.I,
)
_WORD_RE = re.compile(r'[А-ЯЁа-яё-]{3,}')
_EXECUTOR_QUALIFIERS = {'ночь','день','смена','ночная','дневная','утро','вечер'}
_EXECUTOR_EXCLUDE = {'заказчик','камсс'}


def _surnameish_title(word):
    return bool(re.fullmatch(r'[А-ЯЁ][а-яё-]{2,}', word)) and bool(_SURNAME_RE.fullmatch(word.casefold()))


def build_executor_name_set(works, graph_daily):
    """Словарь фамилий из колонки исполнителей + аккуратное обучение по заметкам."""
    known=set()
    for work in works:
        for word in _WORD_RE.findall(str(work.get('executors') or '')):
            low=word.casefold()
            if low not in _EXECUTOR_QUALIFIERS and low not in _EXECUTOR_EXCLUDE:
                known.add(low)

    # В заметках встречаются исполнители, которых нет в колонке C, а также
    # опечатки. Учим только фамилии, стоящие рядом с уже известной фамилией;
    # это не позволяет словам «Монтаж», «Диагностика» стать исполнителями.
    for _ in range(3):
        added=set()
        for dmap in graph_daily.values():
            for fact in dmap.values():
                for line in clean_comment(fact.get('comment','')).splitlines():
                    line=line.strip()
                    if not line:
                        continue
                    matches=list(_WORD_RE.finditer(line))
                    known_indexes=[i for i,m in enumerate(matches) if m.group(0).casefold() in known]
                    if not known_indexes:
                        continue
                    for idx,m in enumerate(matches):
                        word=m.group(0)
                        low=word.casefold()
                        if low in known or low in _EXECUTOR_QUALIFIERS:
                            continue
                        if not _surnameish_title(word):
                            continue
                        # Не захватываем слова из описания, отделённые точкой/двоеточием.
                        nearest=min(known_indexes, key=lambda x: abs(x-idx))
                        lo=min(idx,nearest); hi=max(idx,nearest)
                        bad_sep=False
                        for j in range(lo,hi):
                            sep=line[matches[j].end():matches[j+1].start()]
                            if re.search(r'[.!?:/]', sep):
                                bad_sep=True
                                break
                        if not bad_sep:
                            added.add(low)
        delta=added-known
        if not delta:
            break
        known.update(delta)
    return known


def split_comment_description_executors(comment, known_names):
    """Разделяет текст заметки на описание и исполнителей, удаляя пустые строки."""
    comment=clean_comment(comment)
    if not comment:
        return '', ''

    description_lines=[]
    executor_names=[]

    for raw in comment.splitlines():
        line=re.sub(r'[ \t]+',' ',raw).strip()
        if not line:
            continue
        matches=list(_WORD_RE.finditer(line))
        known_indexes=[i for i,m in enumerate(matches) if m.group(0).casefold() in known_names]
        if not known_indexes:
            description_lines.append(line)
            continue

        start_i=known_indexes[0]
        end_i=known_indexes[-1]

        # Подхватываем неизвестную/опечатанную фамилию рядом с известными.
        while start_i>0:
            prev=matches[start_i-1]; cur=matches[start_i]
            sep=line[prev.end():cur.start()]
            word=prev.group(0)
            if re.search(r'[.!?:/]',sep):
                break
            if word.casefold() in known_names or _surnameish_title(word):
                start_i-=1
            else:
                break
        while end_i+1<len(matches):
            cur=matches[end_i]; nxt=matches[end_i+1]
            sep=line[cur.end():nxt.start()]
            word=nxt.group(0)
            if re.search(r'[.!?:/]',sep):
                break
            if word.casefold() in known_names or _surnameish_title(word):
                end_i+=1
            else:
                break

        name_matches=matches[start_i:end_i+1]
        if not name_matches:
            description_lines.append(line)
            continue

        # Внутри выделенного хвоста не должно быть обычного текста.
        bad=False
        names=[]
        for m in name_matches:
            word=m.group(0)
            low=word.casefold()
            if low in known_names or _surnameish_title(word):
                names.append(word)
            elif low not in _EXECUTOR_QUALIFIERS:
                bad=True
                break
        if bad or not names:
            description_lines.append(line)
            continue

        start=name_matches[0].start()
        end=name_matches[-1].end()
        qualifier=''
        qual_match=re.match(r'\s*\((ночь|день|смена)\)', line[end:], re.I)
        if qual_match:
            qualifier=' ('+qual_match.group(1)+')'
            end += qual_match.end()
            if names:
                names[-1]+=qualifier

        prefix=line[:start].strip().rstrip(' ,;:-–—')
        suffix=line[end:].strip().lstrip(' ,;:.–—-')

        # Один исполнитель внутри длинной фразы может быть частью текста.
        # Выделяем его только если он находится в конце строки/отдельном блоке.
        if len(names)==1 and suffix:
            description_lines.append(line)
            continue

        if prefix:
            description_lines.append(prefix)
        if suffix:
            description_lines.append(suffix)
        executor_names.extend(names)

    # Удаляем повторы, сохраняя порядок.
    unique=[]; seen=set()
    for name in executor_names:
        key=re.sub(r'\s*\([^)]*\)$','',name).casefold()
        if key not in seen:
            seen.add(key)
            unique.append(name.rstrip('.'))

    return '\n'.join(description_lines).strip(), ', '.join(unique)

def sim_tokens(a,b):
    ta=set(re.findall(r'[A-ZА-ЯЁ0-9]{4,}',str(a or '').upper()))
    tb=set(re.findall(r'[A-ZА-ЯЁ0-9]{4,}',str(b or '').upper()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, min(len(ta), len(tb)))

def infer_comment_type(comment):
    text=str(comment or '').lower()
    if any(k in text for k in ('мониторинг','вибротест','plm','vhms')):
        return 'Мониторинг состояния'
    if any(k in text for k in ('капитальн', 'кап. ремонт', 'капремонт')):
        return 'Плановый ремонт'
    if 'модерниз' in text:
        return 'Модернизация'
    if re.search(r'(^|\s)то($|\s|[-–—])', text):
        return 'ТО'
    if any(k in text for k in ('силами полюс','силами заказчика','воздействие полюс')):
        return 'Работы заказчика'
    # Важно: простой в исходнике определяется только символом >.
    return 'Аварийный ремонт'

def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as fh:
        w=csv.DictWriter(fh, fieldnames=fields, extrasaction='ignore', delimiter=';')
        w.writeheader()
        for row in rows:
            w.writerow(row)

class XLSXReader:
    def __init__(self,path):
        self.zf=zipfile.ZipFile(path)
        self.names=set(self.zf.namelist())
        self.shared=[]
        if 'xl/sharedStrings.xml' in self.names:
            root=ET.fromstring(self.zf.read('xl/sharedStrings.xml'))
            for si in root.findall('m:si',NS):
                self.shared.append(''.join((t.text or '') for t in si.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')))
        wb=ET.fromstring(self.zf.read('xl/workbook.xml'))
        rels=ET.fromstring(self.zf.read('xl/_rels/workbook.xml.rels'))
        rid={r.attrib['Id']:r.attrib['Target'] for r in rels}
        self.sheets=[]
        for s in wb.find('m:sheets',NS):
            ridv=s.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
            target=rid[ridv]
            if not target.startswith('xl/'):
                target='xl/'+target.lstrip('/')
            self.sheets.append((s.attrib['name'],target,s.attrib.get('state','visible')))
        styles=ET.fromstring(self.zf.read('xl/styles.xml'))
        self.fills=[]
        for fill in styles.find('m:fills',NS):
            pf=fill.find('m:patternFill',NS)
            info={}
            if pf is not None:
                info['patternType']=pf.attrib.get('patternType')
                fg=pf.find('m:fgColor',NS)
                if fg is not None: info['fg']=dict(fg.attrib)
            self.fills.append(info)
        self.xf_fillids=[int(x.attrib.get('fillId','0')) for x in styles.find('m:cellXfs',NS)]
        self.sheet_path={n:p for n,p,_ in self.sheets}

    def _cell_value(self,c):
        t=c.attrib.get('t')
        v=c.find('m:v',NS)
        if t=='inlineStr':
            isel=c.find('m:is',NS)
            return '' if isel is None else ''.join((x.text or '') for x in isel.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t'))
        if v is None:
            return None
        txt=v.text
        if t=='s':
            try: return self.shared[int(txt)]
            except Exception: return txt
        if t=='b': return txt=='1'
        if t in ('str','e'): return txt
        try:
            x=float(txt)
            return int(x) if x.is_integer() else x
        except Exception:
            return txt

    def parse_sheet(self,name,comments=False):
        path=self.sheet_path[name]
        root=ET.fromstring(self.zf.read(path))
        cells={}; hidden=set()
        sd=root.find('m:sheetData',NS)
        for row in sd.findall('m:row',NS):
            r=int(row.attrib['r'])
            if row.attrib.get('hidden') in ('1','true','True'):
                hidden.add(r)
            for c in row.findall('m:c',NS):
                ref=c.attrib['r']
                s=int(c.attrib.get('s','0'))
                fill=self.xf_fillids[s] if s<len(self.xf_fillids) else 0
                cells[ref]={'v':self._cell_value(c),'s':s,'fill':fill}
        com={}
        if comments:
            base=posixpath.dirname(path)
            relpath=base+'/_rels/'+posixpath.basename(path)+'.rels'
            if relpath in self.names:
                rr=ET.fromstring(self.zf.read(relpath))
                for rel in rr:
                    if rel.attrib.get('Type','').endswith('/comments'):
                        cp=posixpath.normpath(posixpath.join(base,rel.attrib['Target']))
                        cr=ET.fromstring(self.zf.read(cp))
                        for x in cr.findall('.//m:comment',NS):
                            com[x.attrib['ref']]=''.join((t.text or '') for t in x.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t'))
        return cells,hidden,com


def get(cells,ref,default=None):
    return cells.get(ref,{}).get('v',default)


def main():
    OUTROOT.mkdir(parents=True,exist_ok=True)
    CUSTOMER_DIR.mkdir(parents=True,exist_ok=True)
    AUDIT_DIR.mkdir(parents=True,exist_ok=True)
    r=XLSXReader(XLSX)
    graph, hidden_rows, comments = r.parse_sheet('График по работам',comments=True)
    lm,_,_=r.parse_sheet('Список машин')

    # Graph equipment = primary population.
    graph_eq=[]
    for row in range(10,130):
        model=get(graph,f'D{row}'); serial=get(graph,f'E{row}'); garage=get(graph,f'F{row}')
        if model or serial or garage:
            graph_eq.append({
                'graph_row':row,'model':str(model or '').strip(),'serial':str(serial or '').strip(),
                'garage':str(garage or '').strip(),'written_off':row in hidden_rows,'source':'График по работам',
            })
    for x in graph_eq:
        x['cm']=norm_model(x['model']); x['cs']=norm_serial(x['serial']); x['cg']=norm_garage(x['garage'])

    # List equipment, five side-by-side blocks.
    blocks=[('B','C','D','F'),('G','H','I','J'),('M','N','O','P'),('T','U','V','W'),('Z','AA','AB','AC')]
    list_eq=[]
    for row in range(4,130):
        for gc,mc,sc,stc in blocks:
            garage=get(lm,f'{gc}{row}'); model=get(lm,f'{mc}{row}'); serial=get(lm,f'{sc}{row}'); status=get(lm,f'{stc}{row}')
            if model in (None,'') or garage in (None,''):
                continue
            model=str(model).strip()
            if model.lower() in ('график работ','хронология воздействий'):
                continue
            x={'list_row':row,'block':gc,'model':model,'serial':str(serial or '').strip(),'garage':str(garage).strip(),
               'status_text':str(status or '').strip(),'source':'Список машин'}
            x['cm']=norm_model(x['model']); x['cs']=norm_serial(x['serial']); x['cg']=norm_garage(x['garage'])
            list_eq.append(x)

    masters=[dict(x) for x in graph_eq]
    list_only=[]
    for item in list_eq:
        candidates=[m for m in masters if m['cm']==item['cm'] and m['cg']==item['cg']]
        how='model+garage'
        if len(candidates)!=1 and item['cs']:
            candidates=[m for m in masters if m['cm']==item['cm'] and m['cs']==item['cs']]
            how='model+serial'
        if len(candidates)!=1 and item['cs']:
            candidates=[m for m in masters if m['cs']==item['cs'] and m['cg']==item['cg']]
            how='serial+garage'
        if len(candidates)==1:
            m=candidates[0]
            if re.search(r'(?i)\bсписан\b',item['status_text']):
                m['written_off']=True
            m.setdefault('list_matches',[]).append({'row':item['list_row'],'block':item['block'],'how':how})
        else:
            x=dict(item)
            x['written_off']=bool(re.search(r'(?i)\bсписан\b',item['status_text']))
            x['graph_row']=None
            masters.append(x); list_only.append(x)

    for uid,m in enumerate(masters,1):
        m['uid']=uid

    # Build graph date columns: G..BED, but AK is the invalid 31-Sep template column.
    date_by_col={}; d=GRAPH_START
    for c in range(col_to_num('G'),col_to_num('BED')+1):
        if c==col_to_num('AK'):
            continue
        date_by_col[c]=d; d+=timedelta(days=1)
    assert date_by_col[col_to_num('BED')]==GRAPH_END

    # Daily graph facts per equipment.
    graph_daily=defaultdict(dict)
    graph_master_by_row={m['graph_row']:m for m in masters if m.get('graph_row')}
    raw_graph_type_counts=Counter()
    unknown_comment_cells=[]
    for row,m in graph_master_by_row.items():
        for c,dt in date_by_col.items():
            ref=f'{num_to_col(c)}{row}'
            cell=graph.get(ref)
            if cell is None:
                continue
            value=cell['v']; fill=cell['fill']; comment=clean_comment(comments.get(ref,''))
            typ='Простой' if str(value).strip()=='>' else FILL_TYPE.get(fill)
            if not typ and not comment:
                continue
            graph_daily[m['uid']][dt]={'type':typ,'comment':comment,'value':value,'fill':fill,'ref':ref}
            if typ: raw_graph_type_counts[typ]+=1
            elif comment:
                unknown_comment_cells.append({'model':m['model'],'garage':m['garage'],'date':dt.isoformat(),'cell':ref,'fill_id':fill,'comment':comment})

    # Individual machine sheets + mapping to master population.
    individual=[n for n,_,_ in r.sheets[3:]]
    mapped_sheets=[]; out_of_scope=[]
    for name in individual:
        cells,_,_=r.parse_sheet(name)
        model=str(get(cells,'D1') or '').strip(); serial=str(get(cells,'D2') or '').strip()
        mt=re.search(r'#\s*([^\(\n]+)',name)
        garage=mt.group(1).strip() if mt else ''
        item={'sheet':name,'model':model,'serial':serial,'garage':garage,'cm':norm_model(model),'cs':norm_serial(serial),'cg':norm_garage(garage),'cells':cells}
        candidates=[m for m in masters if m['cm']==item['cm'] and m['cg']==item['cg']]
        how='model+garage'
        if len(candidates)!=1 and item['cs']:
            candidates=[m for m in masters if m['cm']==item['cm'] and m['cs']==item['cs']]
            how='model+serial'
        if len(candidates)!=1 and item['cs']:
            candidates=[m for m in masters if m['cs']==item['cs'] and m['cg']==item['cg']]
            how='serial+garage'
        if len(candidates)==1:
            mapped_sheets.append((item,candidates[0],how))
        else:
            out_of_scope.append({'sheet':name,'model':model,'serial':serial,'garage':garage,'reason':'Нет в Графике по работам + Списке машин'})

    # Current hours from explicit sheet field, otherwise maximum machine-hour reading in H.
    hours_candidates=defaultdict(list)
    explicit_hours=defaultdict(list)
    for item,m,how in mapped_sheets:
        cells=item['cells']
        for ref,dv in cells.items():
            if isinstance(dv['v'],str) and 'наработка техники' in dv['v'].lower():
                col,row=cell_parts(ref); val=get(cells,f'{num_to_col(col)}{row+1}')
                try: explicit_hours[m['uid']].append(float(val))
                except Exception: pass
        maxrow=max([cell_parts(x)[1] for x in cells] or [5])
        for row in range(6,maxrow+1):
            val=get(cells,f'H{row}')
            try:
                v=float(val)
                if 0 <= v < 1_000_000: hours_candidates[m['uid']].append(v)
            except Exception: pass
    for m in masters:
        vals=explicit_hours[m['uid']] or hours_candidates[m['uid']]
        m['current_hours']=max(vals) if vals else 0.0

    # Parse work-history rows from mapped sheets.
    works=[]; skipped=[]
    for item,m,how in mapped_sheets:
        cells=item['cells']; maxrow=max([cell_parts(x)[1] for x in cells] or [5])
        for row in range(6,maxrow+1):
            raw_start=get(cells,f'A{row}'); desc=str(get(cells,f'D{row}') or '').strip()
            if raw_start in (None,'') and not desc:
                continue
            start=parse_excel_date(raw_start)
            if not start:
                skipped.append({'sheet':item['sheet'],'row':row,'raw_start':raw_start,'description':desc,'reason':'Нет/не распознана дата начала'})
                continue
            catraw=get(cells,f'E{row}')
            try: cat=int(float(catraw)) if catraw not in (None,'') else None
            except Exception: cat=None
            # Technical rows with only a current-hours marker are not work records.
            if cat is None and desc.strip().lower() in ('','наработка','наработка техники'):
                skipped.append({'sheet':item['sheet'],'row':row,'raw_start':raw_start,'description':desc,'reason':'Техническая строка наработки/пустая'})
                continue
            end=parse_excel_date(get(cells,f'G{row}'))
            status=str(get(cells,f'F{row}') or '').strip()
            req=str(get(cells,f'B{row}') or '').strip()
            ex=str(get(cells,f'C{row}') or '').strip()
            hrs=get(cells,f'H{row}')
            try: hrs=float(hrs) if hrs not in (None,'') else 0.0
            except Exception: hrs=0.0
            report=str(get(cells,f'I{row}') or '').strip().lower()
            works.append({
                'master_uid':m['uid'],'sheet':item['sheet'],'row':row,
                'start_raw':start,'start':start,'end_raw':end,'end':end,
                'cat':cat,'type':CAT_MAP.get(cat),'status':status,'request':req,'executors':ex,
                'description':desc,'machine_hours':hrs,'report_completed':1 if 'да' in report else 0,
                'raw_start_value':raw_start,'raw_end_value':get(cells,f'G{row}'),
                'source':'individual',
            })

    # Разбираем исполнителей из заметок дневного графика. Оригинальный
    # comment сохраняем для сопоставления карточек; description/executors
    # используются при записи work_daily_log.
    known_executor_names=build_executor_name_set(works, graph_daily)
    comment_executor_audit=[]
    for uid,dmap in graph_daily.items():
        m=next((x for x in masters if x['uid']==uid),None)
        for dt,fact in dmap.items():
            parsed_desc,parsed_exec=split_comment_description_executors(
                fact.get('comment',''), known_executor_names
            )
            fact['description']=parsed_desc
            fact['comment_executors']=parsed_exec
            if parsed_exec:
                comment_executor_audit.append({
                    'model':m['model'] if m else '',
                    'garage':m['garage'] if m else '',
                    'date':dt.isoformat(),
                    'cell':fact.get('ref',''),
                    'description':parsed_desc,
                    'executors':parsed_exec,
                })

    date_audit=[]
    # First pass: obvious year/copy errors in start/end.
    for w in works:
        orig_s=w['start']; orig_e=w['end']
        correction=''
        # Future start clearly outside graph horizon. Prefer an explicit end-year fix;
        # if no end exists, search the same month/day in the authoritative daily graph.
        if w['start'] > GRAPH_END:
            cand=None
            if w['end']:
                try:
                    cand=w['start'].replace(year=w['end'].year)
                except ValueError:
                    cand=None
                if cand and cand <= w['end'] and cand >= date(2010,1,1):
                    w['start']=cand; correction='Год начала заменён на год окончания'
            if w['start'] > GRAPH_END:
                dmap=graph_daily[w['master_uid']]
                same_md=[]
                for gd, fact in dmap.items():
                    if gd.month==orig_s.month and gd.day==orig_s.day and (fact.get('type') or fact.get('comment')):
                        score=sim_tokens(w['description'], fact.get('comment',''))
                        if w.get('type') and fact.get('type')==w.get('type'):
                            score += 0.35
                        same_md.append((score,gd,fact))
                same_md.sort(key=lambda x:x[0], reverse=True)
                if same_md and (same_md[0][0] >= 0.25 or len(same_md)==1):
                    w['start']=same_md[0][1]
                    correction=(correction+'; ' if correction else '')+'Дата начала восстановлена по совпадающему дню/комментарию графика'
        # End before start: first try a simple copied-year correction. If it still
        # remains invalid, discard the bad end here and recover it from the graph below.
        if w['end'] and w['end'] < w['start']:
            try:
                cand=w['end'].replace(year=w['start'].year)
            except ValueError:
                cand=None
            if cand and cand >= w['start']:
                w['end']=cand; correction=(correction+'; ' if correction else '')+'Год окончания заменён на год начала'
            else:
                w['end']=None
                correction=(correction+'; ' if correction else '')+'Исходное окончание раньше начала; требуется восстановление по графику'
        # Absurd far-future end / decade-long copy error.
        if w['end'] and (w['end'] > GRAPH_END + timedelta(days=370) or (w['end']-w['start']).days > 1500):
            try:
                cand=w['end'].replace(year=w['start'].year)
            except ValueError:
                cand=None
            if cand and cand >= w['start'] and (cand-w['start']).days <= 400:
                w['end']=cand; correction=(correction+'; ' if correction else '')+'Год окончания приведён к году начала'
        if correction:
            date_audit.append({
                'model':next(m['model'] for m in masters if m['uid']==w['master_uid']),
                'garage':next(m['garage'] for m in masters if m['uid']==w['master_uid']),
                'sheet':w['sheet'],'row':w['row'],'description':w['description'],
                'source_start':orig_s.isoformat() if orig_s else '', 'source_end':orig_e.isoformat() if orig_e else '',
                'final_start':w['start'].isoformat(),'final_end':w['end'].isoformat() if w['end'] else '',
                'method':correction,'review':'Да',
            })

    # Infer missing work type from graph start day / description.
    for w in works:
        if w['type']:
            continue
        gd=graph_daily[w['master_uid']].get(w['start'])
        if gd and gd.get('type') and gd['type']!='Простой':
            w['type']=gd['type']
            w['type_inferred']='По цвету графика на дату начала'
        else:
            text=w['description'].lower()
            if 'то' in text and ('треб' in text or text.strip().startswith('то')):
                w['type']='ТО'
            elif any(k in text for k in ('вибротест','мониторинг','plm','vhms')):
                w['type']='Мониторинг состояния'
            else:
                w['type']='Аварийный ремонт'
            w['type_inferred']='По описанию/резервное правило'

    by_uid=defaultdict(list)
    for w in works: by_uid[w['master_uid']].append(w)
    for ws in by_uid.values(): ws.sort(key=lambda x:(x['start'],x['sheet'],x['row']))

    # Missing ends: recover from graph when possible; otherwise keep a one-day closed history record.
    for uid,ws in by_uid.items():
        dmap=graph_daily[uid]
        starts=sorted(set(w['start'] for w in ws))
        for w in ws:
            if w['end'] is not None:
                # Flag closed records that extend beyond graph horizon, but don't silently change plausible same-year dates.
                if 'закрыт' in w['status'].lower() and w['end'] > GRAPH_END:
                    date_audit.append({
                        'model':next(m['model'] for m in masters if m['uid']==uid),'garage':next(m['garage'] for m in masters if m['uid']==uid),
                        'sheet':w['sheet'],'row':w['row'],'description':w['description'],
                        'source_start':w['start_raw'].isoformat(),'source_end':w['end_raw'].isoformat() if w['end_raw'] else '',
                        'final_start':w['start'].isoformat(),'final_end':w['end'].isoformat(),'method':'Закрытая запись заканчивается после горизонта графика — оставлено как в Excel','review':'Да',
                    })
                continue
            next_dates=[x for x in starts if x>w['start']]
            next_start=next_dates[0] if next_dates else None
            # Conservative limit: next work start, otherwise max 365 days / graph end.
            limit=min(GRAPH_END, w['start']+timedelta(days=365))
            if next_start:
                limit=min(limit,next_start-timedelta(days=1))
            recovered=None; method=''
            if w['start'] <= GRAPH_END and limit >= GRAPH_START:
                search_start=max(w['start'],GRAPH_START)
                anchor=None
                for k in range(0,15):
                    dd=search_start+timedelta(days=k)
                    if dd>limit: break
                    fact=dmap.get(dd)
                    if fact and (fact.get('type') or fact.get('comment')):
                        # Prefer same category, but downtime may be part of a repair.
                        if fact.get('type') in (w['type'],'Простой') or fact.get('comment'):
                            anchor=dd; break
                if anchor:
                    last=anchor; cur=anchor+timedelta(days=1); blank=0
                    while cur<=limit:
                        fact=dmap.get(cur)
                        if fact and (fact.get('type') or fact.get('comment')):
                            last=cur; blank=0
                        else:
                            blank += 1
                            if blank>=2:
                                break
                        cur += timedelta(days=1)
                    recovered=last; method='Восстановлено по дневному графику'
            if recovered is None:
                recovered=w['start']; method='Нет надёжного продолжения в графике — окончание = дата начала'
            w['end']=recovered
            date_audit.append({
                'model':next(m['model'] for m in masters if m['uid']==uid),'garage':next(m['garage'] for m in masters if m['uid']==uid),
                'sheet':w['sheet'],'row':w['row'],'description':w['description'],
                'source_start':w['start_raw'].isoformat(),'source_end':'',
                'final_start':w['start'].isoformat(),'final_end':w['end'].isoformat(),
                'method':method,'review':'Нет' if method.startswith('Восстановлено') else 'Да',
            })

    # Ensure no remaining invalid ranges.
    for w in works:
        if w['end'] and w['end'] < w['start']:
            date_audit.append({
                'model':next(m['model'] for m in masters if m['uid']==w['master_uid']),'garage':next(m['garage'] for m in masters if m['uid']==w['master_uid']),
                'sheet':w['sheet'],'row':w['row'],'description':w['description'],
                'source_start':w['start_raw'].isoformat(),'source_end':w['end_raw'].isoformat() if w['end_raw'] else '',
                'final_start':w['start'].isoformat(),'final_end':w['start'].isoformat(),'method':'Защитная коррекция: окончание = начало','review':'Да',
            })
            w['end']=w['start']

    # Create fresh DB using the exact current project migrations.
    if DB_PATH.exists(): DB_PATH.unlink()
    for ext in ('-wal','-shm'):
        p=Path(str(DB_PATH)+ext)
        if p.exists(): p.unlink()
    sys.path.insert(0,str(PROJECT))
    from database.migrations import migrate
    migrate(db_path=DB_PATH)
    conn=sqlite3.connect(DB_PATH)
    conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')

    # Equipment + standard intervals.
    uid_to_db={}
    for m in masters:
        cur=conn.execute('''INSERT INTO equipment(model,serial_number,garage_number,registration_number,manufacture_year,current_hours,status,note,shift_hours_per_day,auto_maintenance,commissioning_date,warranty_years,warranty_hours,warranty_start_hours,photo_path,manufacturer_id,distributor_id,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(
            m['model'],m['serial'] or 'Н/Д',m['garage'],'',None,float(m['current_hours'] or 0),
            'Списан' if m['written_off'] else 'В работе','Импорт из ежедневной сводки Excel',22.0,0,'',0,0,0,'',KOMATSU_BUILTIN_ID,None,NOW_STR,NOW_STR))
        eid=cur.lastrowid; uid_to_db[m['uid']]=eid
        for hours,name,order in ((50,'ТО-50',10),(250,'ТО-250',20),(500,'ТО-500',30),(1000,'ТО-1000',40),(2000,'ТО-2000',50),(4000,'ТО-4000',60)):
            conn.execute('INSERT INTO maintenance_intervals(equipment_id,interval_hours,name,active,sort_order,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',
                         (eid,hours,name,1,order,NOW_STR,NOW_STR))

    # Work headers.
    work_db_id={}
    for idx,w in enumerate(works):
        closed='закрыт' in w['status'].lower()
        in_progress=0 if closed else 1
        # Historical imported TO is factual, not a future unstarted maintenance plan.
        is_planned=0; is_started=1 if w['type']=='ТО' else 0
        master_for_work=next(m for m in masters if m['uid']==w['master_uid'])
        authoritative_from = GRAPH_START.isoformat() if master_for_work.get('graph_row') else None
        cur=conn.execute('''INSERT INTO work_records(equipment_id,request_number,repair_type,date_start,date_end,in_progress,machine_hours,description,executors,requires_report,report_completed,is_planned,is_started,is_auto_generated,daily_log_authoritative_from,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(
            uid_to_db[w['master_uid']],w['request'],w['type'],w['start'].isoformat(),w['end'].isoformat() if w['end'] else None,
            in_progress,float(w['machine_hours'] or 0),w['description'],w['executors'],0,int(w['report_completed']),is_planned,is_started,0,authoritative_from,NOW_STR,NOW_STR))
        wid=cur.lastrowid; w['db_id']=wid; work_db_id[idx]=wid

    # Candidate scorer for assigning each Excel graph day to one work card.
    synthetic=[]; daily_rows=[]; unresolved_unknown=[]
    # Create synthetic work lazily per contiguous unmatched run, grouped later.
    unmatched_days=defaultdict(list)

    for uid,dmap in graph_daily.items():
        ws=by_uid.get(uid,[])
        for dt,fact in sorted(dmap.items()):
            dtype=fact.get('type')
            comment=fact.get('comment','')
            candidates=[]
            for w in ws:
                if w['start'] <= dt <= (w['end'] or w['start']):
                    score=0.0
                    if dtype and dtype==w['type']: score += 6
                    if dtype=='Простой' and w['type'] in UNAVAILABLE: score += 3
                    if dt==w['start']: score += 3
                    if comment:
                        score += 4*sim_tokens(comment,w['description'])
                        if w['request'] and w['request'].lower() in comment.lower(): score += 3
                    score -= min((dt-w['start']).days,365)/1000
                    candidates.append((score,w))
            if candidates:
                candidates.sort(key=lambda x:x[0],reverse=True)
                w=candidates[0][1]
                if not dtype:
                    dtype=w['type']
                if fact.get('comment_executors'):
                    daily_desc=fact.get('description') or w['description']
                else:
                    daily_desc=fact.get('description') or comment or w['description']
                daily_exec=fact.get('comment_executors') or w['executors']
                daily_rows.append((w['db_id'],dt,dtype,daily_desc,daily_exec,0.0,fact['ref']))
            else:
                unmatched_days[uid].append((dt,fact))

    # Group unmatched graph days into contiguous runs. A comment-only cell is
    # classified from its comment; only a literal > is allowed to become Простой.
    for uid,items in unmatched_days.items():
        for dt, fact in items:
            if not fact.get('type') and fact.get('comment'):
                fact['type']=infer_comment_type(fact.get('comment'))
        items=sorted(items,key=lambda x:x[0])
        runs=[]; cur=[]
        for dt,fact in items:
            if not cur:
                cur=[(dt,fact)]; continue
            prev_dt,prev_fact=cur[-1]
            prev_t=prev_fact.get('type'); t=fact.get('type')
            contiguous=(dt-prev_dt).days==1
            compatible=(t==prev_t or t=='Простой' or prev_t=='Простой' or not t or not prev_t)
            if contiguous and compatible:
                cur.append((dt,fact))
            else:
                runs.append(cur); cur=[(dt,fact)]
        if cur: runs.append(cur)
        for run in runs:
            start=run[0][0]; end=run[-1][0]
            non_down=[f.get('type') for _,f in run if f.get('type') and f.get('type')!='Простой']
            header_type=Counter(non_down).most_common(1)[0][0] if non_down else 'Простой'
            comments_run=[(f.get('description') if f.get('comment_executors') else (f.get('description') or f.get('comment',''))) for _,f in run if (f.get('description') if f.get('comment_executors') else (f.get('description') or f.get('comment')))]
            header_desc=comments_run[0] if comments_run else ('Простой по графику: нет персонала/ожидание' if header_type=='Простой' else 'Импортировано из дневного графика Excel')
            curdb=conn.execute('''INSERT INTO work_records(equipment_id,request_number,repair_type,date_start,date_end,in_progress,machine_hours,description,executors,requires_report,report_completed,is_planned,is_started,is_auto_generated,daily_log_authoritative_from,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(
                uid_to_db[uid],'',header_type,start.isoformat(),end.isoformat(),0,0,header_desc,'',0,0,0,1 if header_type=='ТО' else 0,0,GRAPH_START.isoformat(),NOW_STR,NOW_STR))
            wid=curdb.lastrowid
            m=next(x for x in masters if x['uid']==uid)
            synthetic.append({'model':m['model'],'garage':m['garage'],'date_start':start.isoformat(),'date_end':end.isoformat(),'type':header_type,'days':len(run),'description':header_desc})
            for dt,fact in run:
                dtype=fact.get('type') or header_type
                if not fact.get('type'):
                    unresolved_unknown.append({'model':m['model'],'garage':m['garage'],'date':dt.isoformat(),'cell':fact['ref'],'assigned_type':dtype,'comment':fact.get('comment','')})
                synthetic_desc = (
                    fact.get('description') or header_desc
                    if fact.get('comment_executors')
                    else fact.get('description') or fact.get('comment') or header_desc
                )
                daily_rows.append((
                    wid,dt,dtype,
                    synthetic_desc,
                    fact.get('comment_executors') or '',
                    0.0,fact['ref']
                ))

    # Deduplicate per work/date and insert. (Graph has one cell per equipment/day, assignment is single-target.)
    seen=set(); inserted_daily=0; daily_type_counts=Counter()
    for wid,dt,dtype,desc,ex,hrs,ref in daily_rows:
        key=(wid,dt)
        if key in seen: continue
        seen.add(key)
        conn.execute('''INSERT OR REPLACE INTO work_daily_log(work_id,work_date,day_type,description,executors,machine_hours,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)''',
                     (wid,dt.isoformat(),dtype or 'Аварийный ремонт',desc,ex,float(hrs or 0),NOW_STR,NOW_STR))
        inserted_daily += 1; daily_type_counts[dtype or 'Аварийный ремонт'] += 1

    conn.commit()

    # Integrity and control metrics.
    fk=list(conn.execute('PRAGMA foreign_key_check'))
    integrity=conn.execute('PRAGMA integrity_check').fetchone()[0]
    equipment_count=conn.execute('SELECT COUNT(*) FROM equipment').fetchone()[0]
    written_off_count=conn.execute("SELECT COUNT(*) FROM equipment WHERE status='Списан'").fetchone()[0]
    work_count=conn.execute('SELECT COUNT(*) FROM work_records').fetchone()[0]
    daily_count=conn.execute('SELECT COUNT(*) FROM work_daily_log').fetchone()[0]
    work_types={row[0]:row[1] for row in conn.execute('SELECT repair_type,COUNT(*) FROM work_records GROUP BY repair_type ORDER BY repair_type')}
    daily_types={row[0]:row[1] for row in conn.execute('SELECT day_type,COUNT(*) FROM work_daily_log GROUP BY day_type ORDER BY day_type')}
    report_done=conn.execute('SELECT COUNT(*) FROM work_records WHERE report_completed=1').fetchone()[0]
    # Count DB daily > equivalent = downtime days imported.
    downtime_days=conn.execute("SELECT COUNT(*) FROM work_daily_log WHERE day_type='Простой'").fetchone()[0]

    # Main-equipment mapping table.
    equipment_audit=[]
    for m in masters:
        equipment_audit.append({
            'model':m['model'],'serial':m['serial'],'garage':m['garage'],'status':'Списан' if m['written_off'] else 'В работе',
            'current_hours':m['current_hours'],'source':m.get('source',''),'graph_row':m.get('graph_row') or '',
        })

    write_csv(AUDIT_DIR/'equipment.csv',equipment_audit,['model','serial','garage','status','current_hours','source','graph_row'])
    write_csv(AUDIT_DIR/'date_audit.csv',date_audit,['model','garage','sheet','row','description','source_start','source_end','final_start','final_end','method','review'])
    write_csv(AUDIT_DIR/'skipped_rows.csv',skipped,['sheet','row','raw_start','description','reason'])
    write_csv(AUDIT_DIR/'out_of_scope_sheets.csv',out_of_scope,['sheet','model','serial','garage','reason'])
    write_csv(AUDIT_DIR/'synthetic_graph_works.csv',synthetic,['model','garage','date_start','date_end','type','days','description'])
    assigned_by_ref = {ref: dtype for _,_,dtype,_,_,_,ref in daily_rows}
    for row in unknown_comment_cells:
        row['assigned_type'] = assigned_by_ref.get(row['cell'], '')
    write_csv(AUDIT_DIR/'unknown_comment_cells.csv',unknown_comment_cells,['model','garage','date','cell','fill_id','assigned_type','comment'])
    write_csv(AUDIT_DIR/'unknown_comment_assignments.csv',unresolved_unknown,['model','garage','date','cell','assigned_type','comment'])
    write_csv(AUDIT_DIR/'comment_executors.csv',comment_executor_audit,['model','garage','date','cell','description','executors'])

    summary={
        'customer':CUSTOMER,
        'source_excel':XLSX.name,
        'project_zip_basis':'Архив ZIP - WinRAR(1).zip',
        'equipment':equipment_count,
        'written_off':written_off_count,
        'graph_equipment':len(graph_eq),
        'list_equipment':len(list_eq),
        'list_only_equipment':len(list_only),
        'mapped_individual_sheets':len(mapped_sheets),
        'out_of_scope_individual_sheets':len(out_of_scope),
        'source_work_rows_imported':len(works),
        'skipped_source_rows':len(skipped),
        'synthetic_graph_works':len(synthetic),
        'work_records_total':work_count,
        'daily_log_rows':daily_count,
        'graph_literal_downtime_cells':raw_graph_type_counts['Простой'],
        'daily_downtime_rows':downtime_days,
        'report_completed_rows':report_done,
        'date_audit_rows':len(date_audit),
        'date_audit_review_required':sum(1 for x in date_audit if x['review']=='Да'),
        'unknown_graph_comment_cells':len(unknown_comment_cells),
        'graph_comments_with_executors':len(comment_executor_audit),
        'work_types':work_types,
        'daily_types':daily_types,
        'graph_types_raw':dict(raw_graph_type_counts),
        'integrity_check':integrity,
        'foreign_key_errors':len(fk),
        'db_path':str(DB_PATH),
    }
    (OUTROOT/'import_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    report=[]
    report.append(f'# Пробный импорт — {CUSTOMER}')
    report.append('')
    report.append(f'- Исходный Excel: `{XLSX.name}`')
    report.append(f'- Техника: **{equipment_count}**, из неё списано: **{written_off_count}**')
    report.append(f'- Карточек истории из Excel: **{len(works)}**')
    report.append(f'- Синтетических карточек только для сохранения дневного графика: **{len(synthetic)}**')
    report.append(f'- Всего work_records: **{work_count}**')
    report.append(f'- Дневных записей work_daily_log: **{daily_count}**')
    report.append(f'- Дней `>` из Excel: **{raw_graph_type_counts["Простой"]}**; импортировано дней `Простой`: **{downtime_days}**')
    report.append(f'- Дневных заметок, где исполнители вынесены в отдельное поле: **{len(comment_executor_audit)}**')
    report.append(f'- Строк с `ДА` по техотчёту: **{report_done}** (requires_report=0 для всей импортированной истории)')
    report.append(f'- Пропущено исходных строк: **{len(skipped)}**')
    report.append(f'- Карточек старой техники вне согласованного списка: **{len(out_of_scope)}**')
    report.append(f'- Строк аудита дат: **{len(date_audit)}**, требуют ручной проверки: **{summary["date_audit_review_required"]}**')
    report.append(f'- SQLite integrity_check: **{integrity}**, ошибок внешних ключей: **{len(fk)}**')
    report.append('')
    report.append('## Работы по типам')
    for k,v in sorted(work_types.items()): report.append(f'- {k}: {v}')
    report.append('')
    report.append('## Дневные состояния')
    for k,v in sorted(daily_types.items()): report.append(f'- {k}: {v}')
    report.append('')
    report.append('## Принятые правила')
    report.append('- Скрытая строка в `График по работам` = `Списан`.')
    report.append('- `>` = `Простой` независимо от цвета ячейки.')
    report.append('- Компоненты не переносились.')
    report.append('- `Мониторинг состояния` не уменьшает КТГ; `Модернизация` уменьшает КТГ — это уже реализовано в переданном проекте.')
    report.append('- Для импортированной истории `requires_report=0`; если в Excel было `ДА`, установлен `report_completed=1`.')
    report.append('- Дневной график с 01.09.2022 по 18.09.2026 перенесён в `work_daily_log`; из заметок исполнители вынесены в `executors`, пустые строки удалены из описания.')
    report.append('- Старые индивидуальные листы техники, которой нет в согласованном составе (`График по работам` + `Список машин`), в БД не добавлялись и вынесены в аудит.')
    report.append('')
    report.append('## Важно перед окончательной заменой')
    report.append('Проверьте `audit_csv/date_audit.csv`: строки с `review=Да` содержат подозрительные исходные даты. БД является пробной копией и не затрагивает рабочие данные.')
    (OUTROOT/'IMPORT_REPORT.md').write_text('\n'.join(report),encoding='utf-8')

    conn.close()
    print(json.dumps(summary,ensure_ascii=False,indent=2,default=str))

if __name__=='__main__':
    main()
