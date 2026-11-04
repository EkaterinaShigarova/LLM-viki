import copy
import importlib
import pkgutil
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from baikal import knowledge
from baikal.core import ROOT,read_json,atomic_json,sha256
from baikal.science import check


class DocumentKnowledge(unittest.TestCase):
    def fixture(self,root):
        source={'id':'local-fixture','sha256':'a'*64,'report_year':2022,'publication_year':None,
                'pages':3,'extracted_pages':3,'authenticity':'synthetic_control'}
        atomic_json(root/'config/sources.json',{'sources':[source]})
        for n in range(1,4):
            atomic_json(root/'data/processed'/source['sha256']/'pages'/f'{n:04d}.json',
                        {'status':'ok','text':'Synthetic source statement.','method':'native','headings':[],'tables':[],'images':[]})
        p=root/'wiki/notes/local-fixture/section.md';p.parent.mkdir(parents=True)
        p.write_text('# Synthetic note\n\n[local-fixture:p1](../../sources/local-fixture.md#page-1)\n')
        atomic_json(root/'datasets/knowledge_notes.json',{'notes':[{'path':'notes/local-fixture/section.md',
                    'sha256':sha256(p),'title':'Synthetic note','source_id':source['id'],'source_sha256':source['sha256'],
                    'report_year':2022,'pages':[1],'coverage':'selected_subsection_partial','expert_review':False,
                    'evidence':[{'page':1,'quote':'Synthetic source statement.'}],
                    'articles':[],'territories':['Synthetic site'],'indicators':['Synthetic indicator'],'themes':['Synthetic scope']}]})
        return source

    def test_technical_pages_do_not_become_substantive_coverage(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root)
            docs,_=knowledge.corpus_inventory(root)
            result=knowledge.validate(root,True)
            self.assertEqual(docs[0]['ok_pages'],3)
            self.assertEqual(result['distinct_physical_pages_with_notes'],1)
            self.assertFalse(result['full_document_completeness_established'])

    def test_source_or_quote_change_invalidates_note_without_overwriting_it(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);s=self.fixture(root)
            original=(root/'wiki/notes/local-fixture/section.md').read_bytes()
            p=root/'data/processed'/s['sha256']/'pages/0001.json';data=read_json(p);data['text']='Different evidence';atomic_json(p,data)
            with self.assertRaises(ValueError):knowledge.validate(root,True)
            self.assertEqual((root/'wiki/notes/local-fixture/section.md').read_bytes(),original)

    def test_indices_preserve_nonempty_manual_notes_and_are_repeatable(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root);p=root/'wiki/index.md'
            p.write_text('# Old\n\n<!-- HUMAN NOTES -->\nMy personal note\n')
            knowledge.corpus_inventory(root);knowledge.build(root)
            first=p.read_bytes();knowledge.build(root)
            self.assertIn('My personal note',p.read_text());self.assertEqual(first,p.read_bytes())

    def test_normal_build_keeps_knowledge_index_and_curated_articles(self):
        from unittest.mock import patch
        from baikal import wiki
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);w=root/'wiki';(w/'syntheses').mkdir(parents=True)
            atomic_json(root/'config/sources.json',{'sources':[]})
            atomic_json(root/'datasets/knowledge_notes.json',{'notes':[]})
            article=w/'syntheses/curated.md'
            article.write_text('# Curated science\n\n<!-- HUMAN NOTES -->\nDo not erase this.\n')
            (w/'index.md').write_text('# Old index\n\n<!-- HUMAN NOTES -->\nPersonal index note.\n')
            (w/'LOG.md').write_text('# Historical journal\n')
            with patch.object(wiki,'ROOT',root),patch.object(wiki,'WIKI',w),patch.object(wiki,'load_sources',return_value={'sources':[]}):
                wiki.build();first=(w/'index.md').read_bytes();log=(w/'LOG.md').read_bytes()
                wiki.build()
            self.assertEqual(first,(w/'index.md').read_bytes())
            self.assertEqual(log,(w/'LOG.md').read_bytes())
            self.assertIn('coverage.md',first.decode())
            self.assertIn('Personal index note.',first.decode())
            self.assertIn('Do not erase this.',article.read_text())

    def test_unconfirmed_full_coverage_or_expert_status_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root);p=root/'datasets/knowledge_notes.json'
            data=read_json(p);data['notes'][0]['expert_review']=True;atomic_json(p,data)
            with self.assertRaises(ValueError):knowledge.validate(root)

    def test_national_sections_outside_baikal_do_not_become_content_backlog(self):
        import csv
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=self.fixture(root)
            source['wiki_page_ranges']=[[2,2]]
            atomic_json(root/'config/sources.json',{'sources':[source]})
            atomic_json(root/'datasets/knowledge_notes.json',{'notes':[]})
            atomic_json(root/'datasets/corpus_inventory.json',{'documents':[],
                'sections':[{'source_id':source['id'],'section':'1.1','title':'1.1 Other region','start_page':1},
                            {'source_id':source['id'],'section':'1.2','title':'1.2 Baikal section','start_page':2}]})
            knowledge.build(root)
            with (root/'datasets/coverage_matrix.csv').open() as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(rows[0]['coverage'],'outside_baikal_scope')
            self.assertEqual(rows[0]['articles'],'')
            self.assertEqual(rows[1]['coverage'],'not_summarized')


class RetainedScientificEvidence(unittest.TestCase):
    def copy_public(self,root):
        for rel in ['config/sources.json','config/indicators.json','datasets/source_facts.json']:
            p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,p)

    def test_public_metadata_check_does_not_claim_local_original_access(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.copy_public(root);result=check(root)
            self.assertEqual(result['checked_local_excerpts'],0)
            self.assertEqual(result['source_pdf_checksums'],0)
            with self.assertRaises(FileNotFoundError):check(root,True)

    def test_value_period_and_indicator_semantics_cannot_be_swapped(self):
        for field,value in [('value',['9','99']),('observation_period',{'years':[2030]}),('unit','t_water')]:
            with self.subTest(field=field),tempfile.TemporaryDirectory() as d:
                root=Path(d);self.copy_public(root);p=root/'datasets/source_facts.json';data=read_json(p)
                data['facts'][0][field]=value;atomic_json(p,data)
                with self.assertRaises(ValueError):check(root)

    def test_cli_and_imports_need_no_local_inference_component(self):
        import baikal
        for module in pkgutil.iter_modules(baikal.__path__):
            if module.name!='__main__':importlib.import_module('baikal.'+module.name)
        help_text=subprocess.run([sys.executable,'-m','baikal','--help'],cwd=ROOT,capture_output=True,text=True,check=True).stdout
        for command in ['ingest','query','lint','status']:self.assertIn(command,help_text)
        for removed in ['synthesize','prepare-change','apply-change']:self.assertNotIn(removed,help_text)


if __name__=='__main__':unittest.main()
