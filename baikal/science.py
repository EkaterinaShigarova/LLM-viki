"""Source provenance checks for scientific knowledge; no inference runtime."""
import re
from decimal import Decimal,InvalidOperation
from .core import ROOT,read_json,sha256

def validate_claims(result, evidence):
    if (
        not isinstance(result, dict)
        or not isinstance(result.get("claims"), list)
        or not result["claims"]
    ):
        return ["missing claims"]
    allowed = {}
    for e in evidence:
        allowed.setdefault((e["source_id"], e["page"]), []).append(e["quote"])
    errors = []
    for i, c in enumerate(result["claims"]):
        if (
            not isinstance(c, dict)
            or not isinstance(c.get("text"), str)
            or not c["text"].strip()
            or not isinstance(c.get("evidence"), list)
            or not c["evidence"]
        ):
            errors.append(f"claim {i}: missing text/evidence")
            continue
        for ref in c["evidence"]:
            if not isinstance(ref, dict):
                errors.append(f"claim {i}: unsupported citation")
                continue
            key = (ref.get("source_id"), ref.get("page"))
            quote = ref.get("quote")
            if (
                type(ref.get("page")) is not int
                or not isinstance(quote, str)
                or not quote
                or not any(quote in q for q in allowed.get(key, []))
            ):
                errors.append(f"claim {i}: unsupported citation")
    return errors


def check(root=ROOT, require_local=False):
    sources={s['id']:s for s in read_json(root/'config/sources.json')['sources']}
    archive=read_json(root/'datasets/scientific_archive.json',{})
    facts=read_json(root/'datasets/source_facts.json',{})
    refs=archive.get('source_evidence',[])+facts.get('evidence',[])
    refs+=read_json(root/'datasets/editorial_scientific_review.json',{}).get('sources',[])
    unique={};local=0;pdfs=set()
    for ref in refs:
        source=sources.get(ref['source_id'])
        if not source or source.get('sha256')!=ref['sha256'] or not 1<=ref['page']<=source['pages']:
            raise ValueError('Scientific source revision/page mismatch')
        if ref.get('report_year')!=source.get('report_year'):
            raise ValueError('Reporting year mismatch')
        quote=ref.get('quote','')
        if not quote:raise ValueError('Missing scientific source quote')
        unique[(ref['source_id'],ref['sha256'],ref['page'],quote)]=ref
    for ref in unique.values():
        path=root/'data/processed'/ref['sha256']/'pages'/f"{ref['page']:04d}.json"
        if path.exists():
            if ref['quote'] not in read_json(path).get('text',''):raise ValueError('Quote absent from cited physical page')
            local+=1
        elif require_local:raise FileNotFoundError(path)
        pdf=root/'data/raw'/f"{ref['sha256']}.pdf"
        if require_local and ref['sha256'] not in pdfs:
            if sha256(pdf)!=ref['sha256']:raise ValueError('Immutable original changed')
            pdfs.add(ref['sha256'])
    evidence={e['id']:e for e in facts.get('evidence',[])}
    definitions=read_json(root/'config/indicators.json',{}).get('indicators',{})
    for fact in facts.get('facts',[]):
        support=fact['support'];quote=support['quote']
        if quote not in evidence[support['evidence_id']]['quote']:raise ValueError('Fact source binding lost')
        for anchor in fact['anchors']:
            if anchor['quote'] not in evidence[anchor['evidence_id']]['quote']:raise ValueError('Context/year binding lost')
        if fact['value'] is not None:
            literal=fact['value_lexeme']
            if not literal or literal not in quote:raise ValueError('Value borrowed from a different fragment')
            compact=re.sub(r'\s+','',literal).replace(',','.')
            try:
                expected=[Decimal(str(x)) for x in fact['value']] if isinstance(fact['value'],list) else [Decimal(str(fact['value']))]
                actual=[Decimal(x) for x in compact.split('–')] if isinstance(fact['value'],list) else [Decimal(compact)]
            except InvalidOperation as exc:raise ValueError('Unsupported scalar/range representation') from exc
            if actual!=expected or any(not n.is_finite() for n in expected):raise ValueError('Value differs from its own source literal')
            if not fact['unit_lexeme'] or fact['unit_lexeme'] not in quote:raise ValueError('Unit has no own evidence')
            if fact['unit_lexeme'] not in facts['units'].get(fact['unit'],{}).get('lexemes',[]):raise ValueError('Unit interpretation unregistered')
        definition=definitions.get(fact['indicator'])
        if definition:
            for field,allowed in [('unit','units'),('statistic','statistics'),('message_kind','message_kinds')]:
                if fact[field] not in definition[allowed]:raise ValueError('Indicator/unit/statistic meaning mismatch')
        elif definitions:raise ValueError('Indicator undefined')
        if fact['expert_review'] or fact['comparability_approved']:raise ValueError('Unconfirmed expert/trend status')
        period=fact.get('observation_period')
        if period:
            year_quotes=' '.join(a['quote'] for a in fact['anchors'] if a['role']=='period')
            compact=re.sub(r'\s+','',year_quotes)
            if any(str(y) not in compact for y in period['years']):raise ValueError('Year lacks its own evidence')
            if period.get('month'):
                stems=read_json(root/'config/indicators.json')['month_stems'];stem=stems.get(str(period['month']))
                if not stem or not re.search(re.escape(stem),year_quotes,re.I):raise ValueError('Month lacks its own evidence')
    return {'errors':[], 'unique_source_excerpts':len(unique),'checked_local_excerpts':local,
            'source_pdf_checksums':len(pdfs),'source_fact_cards':len(facts.get('facts',[])),
            'expert_review':False}
