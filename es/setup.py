"""Create a versioned products index, bulk-load it and point the `products` alias at it.

Usage:
python -m es.setup_index # create products_v1 and load data/products.jsonl
python -m es.setup_index --recreate # drop and rebuild products_v1
python -m es.setup_index --version 2 # build products_v2, then swap the alias atomically
"""
import argparse
import json
import time
from pathlib import Path

from elasticsearch import Elasticsearch, helpers

from es.client import get_client
from es.mappings import ALIAS, INDEX_MAPPINGS, index_name, index_settings

DEFAULT_DATA = Path(__file__).resolve().parent.parent / "data" / "products.jsonl"


def create_index(es: Elasticsearch, name: str, recreate: bool) -> None:
    if es.indices.exists(index=name):
        if not recreate:
            raise SystemExit(f"Index '{name}' already exists. Use --recreate or a new --version.")
        es.indices.delete(index=name)
        print(f"Deleted existing index {name}")

    settings = index_settings()
    settings["refresh_interval"] = "-1" # no refreshes during the bulk load: much faster indexing
    es.indices.create(index=name, settings=settings, mappings=INDEX_MAPPINGS)
    print(f"Created index {name}")


def bulk_load(es: Elasticsearch, name: str, data_file: Path) -> int:
    def actions():
        with data_file.open(encoding="utf-8") as f:
            for line in f:
                doc = json.loads(line)
                yield {"_index": name, "_id": doc["id"], "_source": doc}

    start = time.perf_counter()
    ok, errors = helpers.bulk(es, actions(), chunk_size=1000, raise_on_error=False)
    for err in errors[:5]:
        print(" bulk error:", err)
    print(f"Indexed {ok:,} docs ({len(errors)} errors) in {time.perf_counter() - start:.1f}s")

    es.indices.put_settings(index=name, settings={"refresh_interval": "1s"})
    es.indices.refresh(index=name)
    return ok


def point_alias(es: Elasticsearch, name: str) -> None:
    """Move the alias to `name` in one atomic call, so searches never see a missing index."""
    actions = [{"add": {"index": name, "alias": ALIAS}}]
    if es.indices.exists_alias(name=ALIAS):
        actions += [
            {"remove": {"index": old, "alias": ALIAS}}
            for old in es.indices.get_alias(name=ALIAS)
            if old != name
        ]
    es.indices.update_aliases(actions=actions)
    print(f"Alias '{ALIAS}' -> {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", type=int, default=1)
    parser.add_argument("--recreate", action="store_true")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    args = parser.parse_args()

    if not args.data.exists():
        raise SystemExit(f"{args.data} not found. Run: python -m data.generate_products")

    es = get_client()
    name = index_name(args.version)
    create_index(es, name, args.recreate)
    bulk_load(es, name, args.data)
    point_alias(es, name)
    print(f"Done. Documents in '{ALIAS}': {es.count(index=ALIAS)['count']:,}")


if __name__ == "__main__":
    main()