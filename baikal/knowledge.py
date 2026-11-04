"""Markdown knowledge inventory: explicit note coverage, source sections and indices.

Detected headings and page intersections are navigation signals, not a claim of
substantive analysis. Only registered agent-written notes count as summaries.
"""
import csv
import io
import re
from pathlib import Path
from .core import ROOT,read_json,atomic_json,atomic_text,sha256


def notes(root=ROOT):
    return read_json(root/'datasets/knowledge_notes.json', {'version':1,'notes':[]})['notes']


def validate(root=ROOT,require_local=False):
    cfg={s['id']:s for s in read_json(root/'config/sources.json',{'sources':[]})['sources']}
    checked=0;seen=set()
    for n in notes(root):
        if n['path'] in seen:raise ValueError('Duplicate document summary')
        seen.add(n['path']);p=(root/'wiki'/n['path']).resolve()
        if not p.is_relative_to((root/'wiki/notes').resolve()) or not p.is_file():raise ValueError('Invalid note path')
        if sha256(p)!=n['sha256']:raise ValueError('Note revision changed; recheck coverage/evidence')
        s=cfg[n['source_id']]
        if n['source_sha256']!=s['sha256'] or n['report_year']!=s['report_year']:raise ValueError('Stale source/note')
        if n['coverage']!='selected_subsection_partial' or n['expert_review']:raise ValueError('Unconfirmed full/expert coverage')
        if not n['evidence'] or sorted({r['page'] for r in n['evidence']})!=sorted(n['pages']):raise ValueError('Note coverage lacks evidence')
        text=p.read_text()
        for r in n['evidence']:
            if not 1<=r['page']<=s['pages'] or not r['quote']:raise ValueError('Invalid note evidence')
            if f"{s['id']}.md#page-{r['page']}" not in text:raise ValueError('Note lacks physical-page link')
            cache=root/'data/processed'/s['sha256']/'pages'/f"{r['page']:04d}.json"
            if cache.exists():
                if r['quote'] not in read_json(cache).get('text',''):raise ValueError('Note quote absent from primary page')
                checked+=1
            elif require_local:raise FileNotFoundError(cache)
        for name in n['articles']:
            if not (root/'wiki'/name).is_file():raise ValueError('Note points to missing synthesis')
    return {'errors':[],'notes':len(seen),'documents_with_notes':len({n['source_id'] for n in notes(root)}),
            'distinct_physical_pages_with_notes':len({(n['source_id'],p) for n in notes(root) for p in n['pages']}),
            'checked_local_note_references':checked,'full_document_completeness_established':False,'expert_review':False}


def corpus_inventory(root=ROOT):
    """Read existing checkpoint JSON/headings. Never invokes extraction or OCR."""
    records=[];sections=[]
    for s in read_json(root/'config/sources.json')['sources']:
        pages=sorted((root/'data/processed'/s['sha256']/'pages').glob('*.json'))
        if not pages:raise FileNotFoundError('Coverage inventory needs original checkpoints')
        record={'source_id':s['id'],'report_year':s.get('report_year'),'publication_year':s.get('publication_year'),
                'source_sha256':s['sha256'],'authenticity':s['authenticity'],'original_path':f"data/raw/{s['sha256']}.pdf",
                'declared_pages':s['pages'],'checkpoint_pages':len(pages),'ok_pages':0,'text_pages':0,'ocr_pages':0,
                'detected_tables':0,'image_occurrences':0,'image_records_without_asset':0,
                'missing_image_files':0,'machine_markdown_pages':0,'candidate_sections':0}
        detected=set()
        for p in pages:
            row=read_json(p);record['ok_pages']+=row['status']=='ok';record['text_pages']+=bool(row.get('text','').strip())
            record['ocr_pages']+=row.get('method','').startswith('ocr')
            record['detected_tables']+=len(row.get('tables',[]));record['image_occurrences']+=len(row.get('images',[]))
            record['machine_markdown_pages']+=(p.parent.parent/'markdown'/f'{p.stem}.md').is_file()
            for image in row.get('images',[]):
                if not image.get('asset'):record['image_records_without_asset']+=1
                elif not (p.parent.parent/image['asset']).is_file():record['missing_image_files']+=1
            for h in row.get('headings',[]):
                title=' '.join(h['text'].split())
                m=re.match(r'^(\d+(?:\.\d+){1,4})\.?\s+([^\d].{5,150})$',title)
                if not m or re.search(r'\.{3}|таблица|рис\.',title,re.I) or int(p.stem)<5:continue
                key=(m[1],title)
                if key in detected:continue
                detected.add(key)
                sections.append({'source_id':s['id'],'section':m[1],'title':title,'start_page':int(p.stem),
                                 'heading_status':'detected_unreviewed_boundary','boundary_completeness':'not_established'})
        record['candidate_sections']=len(detected);records.append(record)
    atomic_json(root/'datasets/corpus_inventory.json',{'version':1,'documents':records,'sections':sections,
                'note':'Detected headings are incomplete navigation aids, not verified chapter boundaries or source summaries.'})
    return records,sections


def build(root=ROOT):
    """Maintain simple Markdown/CSV views of existing agent-written knowledge."""
    if not (root/'datasets/knowledge_notes.json').exists():return {'notes':0}
    from .wiki import write_page
    cfg=read_json(root/'config/sources.json')['sources'];entries=notes(root)
    inventory=read_json(root/'datasets/corpus_inventory.json',{'documents':[],'sections':[]})
    w=root/'wiki';rows=[]
    cov=['# Покрытие исходного корпуса','',
         'Техническое извлечение, конспектирование, тематический синтез и экспертная проверка — разные стадии. '
         'Наличие конспекта отдельных страниц не означает полноты раздела или доклада.','',
         '| Доклад | Технические страницы | Конспекты разделов | Страницы в конспектах | Пробелы |',
         '| --- | ---: | ---: | ---: | --- |']
    for s in sorted(cfg,key=lambda s:s.get('report_year') or 0):
        group=[n for n in entries if n['source_id']==s['id']]
        distinct=sorted({p for n in group for p in n['pages']})
        docdir=w/'notes'/s['id'];docdir.mkdir(parents=True,exist_ok=True)
        lines=[f"# Конспекты доклада {s.get('report_year')}",'',f"Источник: `{s['id']}`; SHA256 `{s['sha256']}`.",'',
               f"[Страницы и оригинал](../../sources/{s['id']}.md)",'',
               'Конспекты ниже охватывают выбранные подразделы; остальные страницы ещё требуют содержательного чтения.','']
        for n in group:lines += [f"- [{n['title']}]({Path(n['path']).name}) — физические PDF-страницы {', '.join(map(str,n['pages']))}."]
        lines += ['', '## Обнаруженные заголовки и открытые пробелы','',
                  'Это машинно найденные заголовки, не гарантированное оглавление. Границы и полноту нужно проверить по документу.','']
        ss=sorted([x for x in inventory['sections'] if x['source_id']==s['id']],key=lambda x:x['start_page'])
        for i,sec in enumerate(ss):
            end=max(sec['start_page'],ss[i+1]['start_page']-1) if i+1<len(ss) else s['pages']
            ranges=s.get('wiki_page_ranges')
            in_scope=not ranges or any(a<=sec['start_page']<=b for a,b in ranges)
            stop=s.get('wiki_stop_before',{}).get(str(sec['start_page']))
            if stop and sec['title'].startswith(stop):in_scope=False
            scope='outside_configured_baikal_scope' if not in_scope else ('configured_baikal_range' if ranges else 'document_scope_unreviewed')
            linked=[n for n in group if in_scope and any(sec['start_page']<=p<=end for p in n['pages'])]
            articles=sorted({a for n in linked for a in n['articles']})
            gap=('partial_selected_pages_only' if linked else 'not_summarized') if in_scope else 'outside_baikal_scope'
            rows.append({'source_id':s['id'],'report_year':s['report_year'],'section':sec['section'],'heading':sec['title'],
                         'start_page':sec['start_page'],'candidate_end_page':end,
                         'notes':' | '.join(n['path'] for n in linked),'themes':' | '.join(sorted({t for n in linked for t in n['themes']})),
                         'articles':' | '.join(articles),'coverage':gap,'boundary_status':'unreviewed_navigation_range','scope_status':scope})
            label='; '.join(f"[{n['title']}]({Path(n['path']).name})" for n in linked) or 'конспекта пока нет'
            if in_scope:
                lines.append(f"- {sec['title']} (PDF{sec['start_page']}): {label}. Полнота раздела не установлена.")
            else:
                lines.append(f"- {sec['title']} (PDF{sec['start_page']}): вне заданного Байкальского раздела обзора; не очередь тематического наполнения.")
        lines += ['','[Покрытие корпуса](../../coverage.md) · [Главный индекс](../../index.md)']
        write_page(docdir/'index.md','\n'.join(lines)+'\n')
        cov.append(f"| [{s.get('report_year')}](notes/{s['id']}/index.md) | {s.get('extracted_pages',0)}/{s['pages']} | {len(group)} | {len(distinct)} | Всё вне явно указанных страниц; полнота внутри них также не утверждается |")
    output=io.StringIO();fields=['source_id','report_year','section','heading','start_page','candidate_end_page','notes','themes','articles','coverage','boundary_status','scope_status']
    writer=csv.DictWriter(output,fieldnames=fields,lineterminator='\n');writer.writeheader();writer.writerows(rows)
    atomic_text(root/'datasets/coverage_matrix.csv',output.getvalue())
    cov+=['','[Машиночитаемая матрица](../datasets/coverage_matrix.csv) содержит предполагаемые диапазоны разделов; '
          'пересечение страниц с конспектом — навигационный сигнал, не подтверждение полноты. '
          'Некоторые заголовки не распознаются; за пределами известных диапазонов также остаются пробелы.','',
          '[Нерешённые вопросы](questions.md) · [Приоритеты](../docs/REMAINING.md)']
    write_page(w/'coverage.md','\n'.join(cov)+'\n')
    for field,title,name in [('report_year','По годам докладов','years'),('territories','По территориям','territories'),('indicators','По показателям и методам','indicators')]:
        groups={}
        for n in entries:
            values=[n[field]] if field=='report_year' else n[field]
            for v in values:groups.setdefault(str(v),[]).append(n)
        text=[f'# {title}','','Индекс конспектов; совпадение названия показателя не разрешает межгодовое сравнение.','']
        for value,group in sorted(groups.items()):
            text += [f'## {value}','']
            for n in group:text += [f"- [{n['title']}](../{n['path']}) — доклад {n['report_year']}."]
            text+=['']
        text+=['[Главный индекс](../index.md)']
        write_page(w/'indexes'/f'{name}.md','\n'.join(text)+'\n')
    index=['# LLM-viki: экологический мониторинг Байкала и БПТ','',
           'Постоянная научная Markdown-база: источники → подробные конспекты → связанные тематические статьи.','',
           '- [Тематический каталог](catalog.md)','- [Конспекты и покрытие корпуса](coverage.md)',
           '- [Годы](indexes/years.md) · [Территории](indexes/territories.md) · [Показатели](indexes/indicators.md)',
           '- [Нерешённые вопросы](questions.md) · [Вход для другого ИИ](AI_READER.md)',
           '- [Журнал](LOG.md) · [Происхождение источников](../SOURCES.md)','','## Тематические статьи','']
    for p in sorted((w/'syntheses').glob('*.md')):index.append(f"- [{p.read_text().splitlines()[0].lstrip('# ')}](syntheses/{p.name})")
    index+=['','## Документы и конспекты','']
    for s in sorted(cfg,key=lambda s:s.get('report_year') or 0):index.append(f"- [Доклад {s.get('report_year')}: конспекты](notes/{s['id']}/index.md) · [первичные страницы](sources/{s['id']}.md)")
    index+=['','## Тематические выдержки и объекты','']
    for folder in ['topics','entities','queries']:
        for p in sorted((w/folder).glob('*.md')):index.append(f"- [{p.read_text().splitlines()[0].lstrip('# ')}]({folder}/{p.name})")
    write_page(w/'index.md','\n'.join(index)+'\n')
    return {'notes':len(entries),'documents_with_notes':len({n['source_id'] for n in entries}),'coverage_rows':len(rows)}
