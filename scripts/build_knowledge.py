"""Maintain note indices; --inventory reads existing checkpoints, never PDF/OCR."""
import argparse
import json
from baikal.knowledge import corpus_inventory,build,validate

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory',action='store_true');args=parser.parse_args()
    validate()
    if args.inventory:corpus_inventory()
    print(json.dumps(build(),ensure_ascii=False,indent=2))
