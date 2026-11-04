"""Check the registered document notes, coverage and Markdown links."""
import argparse
import json
from baikal.knowledge import validate
from baikal.wiki import lint

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-local',action='store_true');args=parser.parse_args()
    try:
        result={'notes':validate(require_local=args.require_local),'wiki':lint()}
        print(json.dumps(result,ensure_ascii=False,indent=2))
        if result['wiki']['errors']:parser.exit(1)
    except (ValueError,OSError,KeyError) as exc:parser.exit(1,f'Knowledge check failed: {exc}\n')
