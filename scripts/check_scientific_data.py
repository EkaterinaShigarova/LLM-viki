"""Check retained scientific evidence without an inference server."""
import argparse
import json
from baikal.science import check
from baikal.scientific_review import validate
from baikal.encyclopedia import check_evidence
from baikal.draft_review import validate as check_drafts

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-local',action='store_true');args=parser.parse_args()
    try:
        result={'scientific_data':check(require_local=args.require_local),
                'article_claims':validate(require_local=args.require_local),
                'encyclopedia':check_evidence(require_local=args.require_local),
                'retained_drafts_and_candidates':check_drafts(require_local=args.require_local)}
        print(json.dumps(result,ensure_ascii=False,indent=2))
        if any(v.get('errors') for v in result.values()):parser.exit(1)
    except (ValueError,OSError,KeyError) as exc:parser.exit(1,f'Scientific evidence check failed: {exc}\n')
