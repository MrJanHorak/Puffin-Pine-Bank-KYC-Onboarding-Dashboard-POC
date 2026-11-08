"""Day 12, lecture lab: run only the extraction stage and check it against the schema.

python -m kit.extract_stage --case CASE-A
python -m kit.extract_stage --case CASE-B --extractor azure
"""
import argparse

import yaml

from kit.common import ROOT, doc_type_of, list_documents
from kit.extract import get_extractor
from kit.review import review_items

try:  # load Azure settings from .env when python-dotenv is installed
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the extraction stage only")
    parser.add_argument("--case", default="CASE-A")
    parser.add_argument("--extractor", choices=["offline", "azure"], default="offline")
    parser.add_argument("--schema", default=str(ROOT / "schema" / "kyc_extraction_schema.yaml"))
    args = parser.parse_args(argv)
    schema = yaml.safe_load(open(args.schema))
    extractor = get_extractor(args.extractor)
    for path in list_documents(args.case):
        doc_type = doc_type_of(path)
        record = extractor.extract(path)
        print(f"\n{path.name}  [{record['source']}]")
        for name, f in record["fields"].items():
            if name == "owners":
                for i, owner in enumerate(f, start=1):
                    for k, v in owner.items():
                        print(f"  owners[{i}].{k:<16} {v['value']!s:<40} {v['confidence']}")
            else:
                print(f"  {name:<26} {f['value']!s:<40} {f['confidence']}")
        items = review_items(path.name.split("_")[0], doc_type, record, schema)
        print(f"  -> schema check: {'OK' if not items else str(len(items)) + ' item(s) for review'}")
        for item in items:
            print(f"     {item['field']}: {item['reason']}")


if __name__ == "__main__":
    main()
