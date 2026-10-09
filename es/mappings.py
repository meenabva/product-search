"""Index settings, analyzers and mappings for the product catalog.

Key design decisions:
- `name` / `description` are `text` fields with an English stemmer. Synonyms are applied only
at SEARCH time (`search_analyzer`), so changing synonyms never needs a reindex.
- `brand` / `category` are `keyword` (exact filtering and facet counts) with a `.text`
sub-field so they are also full-text searchable.
- `variants` and `stores` are `nested`, so "black AND 256GB" matches inside the SAME variant
and each store keeps its own location.
- `name.suggest` (completion) and `name.ngram` (edge n-gram) are ready for autocomplete in
Phase 5. Other autocomplete fields (search_as_you_type, embeddings) come later with a
products_v2 index and an alias swap.
"""
from pathlib import Path

ALIAS = "products" # the app always queries the alias, never a concrete index


def index_name(version: int) -> str:
    return f"{ALIAS}_v{version}"


def load_synonyms(path: Path = Path(__file__).parent / "synonyms.txt") -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]


def index_settings() -> dict:
    return {
        "number_of_shards": 1,
        "number_of_replicas": 0, # single-node cluster: replicas could never be assigned
        "analysis": {
            "filter": {
                "english_stemmer": {"type": "stemmer", "language": "english"},
                "product_synonyms": {"type": "synonym_graph", "synonyms": load_synonyms()},
                "autocomplete_edge": {"type": "edge_ngram", "min_gram": 2, "max_gram": 15},
            },
            "analyzer": {
            # index time: plain tokens, lowercased and stemmed
                "product_text": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "asciifolding", "english_stemmer"],
                },
                # search time: same chain plus synonym expansion (before stemming)
                "product_search": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "asciifolding", "product_synonyms", "english_stemmer"],
                },
                # "iphone" -> ip, iph, ipho, iphon, iphone
                "autocomplete": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "asciifolding", "autocomplete_edge"],
                },
                "autocomplete_search": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "asciifolding"],
                },
            },
        },
    }


def _searchable_keyword() -> dict:
    return {
        "type": "keyword",
        "fields": {"text": {"type": "text", "analyzer": "product_text", "search_analyzer": "product_search"}},
    }


INDEX_MAPPINGS = {
    "dynamic": "strict", # reject documents with unexpected fields instead of guessing types
    "properties": {
        "id": {"type": "keyword"},
        "name": {
            "type": "text",
            "analyzer": "product_text",
            "search_analyzer": "product_search",
            "fields": {
                "keyword": {"type": "keyword", "ignore_above": 256},
                "suggest": {"type": "completion"},
                "ngram": {"type": "text", "analyzer": "autocomplete", "search_analyzer": "autocomplete_search"},
            },
        },
        "description": {"type": "text", "analyzer": "product_text", "search_analyzer": "product_search"},
        "brand": _searchable_keyword(),
        "category": _searchable_keyword(),
        "tags": {"type": "keyword"},
        "price": {"type": "scaled_float", "scaling_factor": 100},
        "rating": {"type": "half_float"},
        "review_count": {"type": "integer"},
        "in_stock": {"type": "boolean"},
        "created_at": {"type": "date"},
        "variants": {
            "type": "nested",
            "properties": {
                "color": {"type": "keyword"},
                "size": {"type": "keyword"},
                "stock": {"type": "integer"},
            },
        },
        "stores": {
            "type": "nested",
            "properties": {
                "store_id": {"type": "keyword"},
                "name": {"type": "keyword"},
                "location": {"type": "geo_point"},
                },
            },
        },
}