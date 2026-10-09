"""Runs searches against Elasticsearch and turns raw responses into API-friendly dicts."""
from elasticsearch import Elasticsearch

from es.mappings import ALIAS
from search.query_builder import SearchParams, build_search_body


def search(es: Elasticsearch, p: SearchParams, debug: bool = False) -> dict:
    body = build_search_body(p)
    resp = es.search(index=ALIAS, body=body)

    result = {
        "total": resp["hits"]["total"]["value"],
        "page": p.page,
        "per_page": p.per_page,
        "took_ms": resp["took"],
        "results": [_format_hit(h) for h in resp["hits"]["hits"]],
        "facets": _format_facets(resp["aggregations"], p),
    }
    if debug:
        result["es_request"] = body
    return result


def get_product(es: Elasticsearch, product_id: str) -> dict:
    return es.get(index=ALIAS, id=product_id)["_source"]


def analyze(es: Elasticsearch, text: str, analyzer: str) -> list[str]:
    """See exactly which tokens an analyzer produces -- great for debugging synonyms and stemming."""
    resp = es.indices.analyze(index=ALIAS, analyzer=analyzer, text=text)
    return [t["token"] for t in resp["tokens"]]


def _format_hit(hit: dict) -> dict:
    src = dict(hit["_source"])
    variants = src.pop("variants", [])
    return {
        **src,
        "colors": sorted({v["color"] for v in variants}),
        "sizes": sorted({v["size"] for v in variants}),
        "score": hit.get("_score"),
        "highlight": hit.get("highlight", {}),
    }


def _format_facets(aggs: dict, p: SearchParams) -> dict:
    def term_buckets(buckets: list[dict], selected: list[str], nested: bool = False) -> list[dict]:
        return [
            {
            "value": b["key"],
            "count": b["products"]["doc_count"] if nested else b["doc_count"],
            "selected": b["key"] in selected,
            }
            for b in buckets
        ]

    def range_buckets(buckets: list[dict]) -> list[dict]:
        return [
        {"key": b["key"], "from": b.get("from"), "to": b.get("to"), "count": b["doc_count"]}
        for b in buckets
        ]

    stats = aggs["price"]["stats"]
    return {
        "brand": term_buckets(aggs["brand"]["values"]["buckets"], p.brand),
        "category": term_buckets(aggs["category"]["values"]["buckets"], p.category),
        "color": term_buckets(aggs["color"]["values"]["terms"]["buckets"], p.color, nested=True),
        "size": term_buckets(aggs["size"]["values"]["terms"]["buckets"], p.size, nested=True),
        "price": range_buckets(aggs["price"]["values"]["buckets"]),
        "price_stats": {k: stats[k] for k in ("min", "max", "avg")},
        "rating": range_buckets(aggs["rating"]["values"]["buckets"]),
    }
