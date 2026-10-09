"""Pure functions that build Elasticsearch request bodies. No ES connection needed,
so you can print and study the generated DSL (the API's `debug=true` returns it too).

How faceting works here:
- `query` holds the full-text part and non-facet filters (in_stock). Scores and ALL facet
counts respect it.
- Selected facet values go into `post_filter`: they narrow the hits but NOT the aggregations.
- Each facet aggregation is wrapped in a `filter` agg that applies every OTHER selected
facet. So after picking brand=Apple, the brand facet still lists Samsung, Sony, ... with
counts, while the color and price facets show only Apple's numbers.
"""
from dataclasses import dataclass, field

MAX_RESULT_WINDOW = 10_000 # ES default index.max_result_window; go deeper with search_after

FACETS = ("brand", "category", "color", "size", "price", "rating")

PRICE_RANGES = [
    {"key": "under-1k", "to": 1_000},
    {"key": "1k-5k", "from": 1_000, "to": 5_000},
    {"key": "5k-20k", "from": 5_000, "to": 20_000},
    {"key": "20k-50k", "from": 20_000, "to": 50_000},
    {"key": "50k-plus", "from": 50_000},
]

RATING_RANGES = [
    {"key": "4-up", "from": 4},
    {"key": "3-up", "from": 3},
    {"key": "2-up", "from": 2},
]

SORTS = {
    "relevance": ["_score", {"review_count": "desc"}],
    "price_asc": [{"price": "asc"}, "_score"],
    "price_desc": [{"price": "desc"}, "_score"],
    "rating": [{"rating": "desc"}, {"review_count": "desc"}],
    "newest": [{"created_at": "desc"}, "_score"],
}

SOURCE_FIELDS = ["id", "name", "brand", "category", "price", "rating", "review_count",
    "in_stock", "created_at", "tags", "variants"]


@dataclass
class SearchParams:
    q: str | None = None
    brand: list[str] = field(default_factory=list)
    category: list[str] = field(default_factory=list)
    color: list[str] = field(default_factory=list)
    size: list[str] = field(default_factory=list)
    price_min: float | None = None
    price_max: float | None = None
    min_rating: float | None = None
    in_stock_only: bool = False
    sort: str = "relevance"
    page: int = 1
    per_page: int = 20


# ---------- query (relevance) ----------

def text_query(q: str) -> dict:
    return {
        "bool": {
            "must": [{
                "multi_match": {
                "query": q,
                "fields": ["name^3", "brand.text^2", "category.text^2", "description"],
                "type": "best_fields",
                "fuzziness": "AUTO", # "iphnoe" still finds "iphone"
                "prefix_length": 1, # first letter must match: fewer junk fuzzy hits
                "minimum_should_match": "2<75%", # <=2 words: all required; more: 75%
                }
            }],
            # bonus when the words appear together, in order, in the name
            "should": [{"match_phrase": {"name": {"query": q, "slop": 1, "boost": 2}}}],
        }
    }


def with_business_boosts(query: dict) -> dict:
    """Add popularity, rating and freshness on top of the text relevance (BM25) score."""
    return {
        "function_score": {
            "query": query,
            "functions": [
                {"field_value_factor": {"field": "review_count", "modifier": "log1p", "factor": 0.1, "missing": 0}},
                {"field_value_factor": {"field": "rating", "missing": 3}, "weight": 0.3},
                {"gauss": {"created_at": {"origin": "now", "scale": "90d", "offset": "7d", "decay": 0.5}}},
            ],
            "score_mode": "sum",
            "boost_mode": "sum",
        }
    }


def build_query(p: SearchParams) -> dict:
    base = text_query(p.q) if p.q else {"match_all": {}}
    if p.in_stock_only:
        base = {"bool": {"must": [base], "filter": [{"term": {"in_stock": True}}]}}
    return with_business_boosts(base)


# ---------- facet filters ----------

def filter_clauses(p: SearchParams, exclude: str | None = None) -> list[dict]:
    """Filter clauses for the selected facet values, optionally leaving one facet out."""
    clauses: list[dict] = []
    if p.brand and exclude != "brand":
        clauses.append({"terms": {"brand": p.brand}})
    if p.category and exclude != "category":
        clauses.append({"terms": {"category": p.category}})

    # color and size share ONE nested query, so both must match within the same variant
    variant = []
    if p.color and exclude != "color":
        variant.append({"terms": {"variants.color": p.color}})
    if p.size and exclude != "size":
        variant.append({"terms": {"variants.size": p.size}})
    if variant:
        clauses.append({"nested": {"path": "variants", "query": {"bool": {"filter": variant}}}})

    if (p.price_min is not None or p.price_max is not None) and exclude != "price":
        rng = {}
        if p.price_min is not None:
            rng["gte"] = p.price_min
        if p.price_max is not None:
            rng["lte"] = p.price_max
        clauses.append({"range": {"price": rng}})
    if p.min_rating is not None and exclude != "rating":
        clauses.append({"range": {"rating": {"gte": p.min_rating}}})
    return clauses


def _nested_variant_terms(field_name: str) -> dict:
    # nested -> terms on the variant field -> reverse_nested: counts PRODUCTS, not variants
    return {
        "nested": {"path": "variants"},
        "aggs": {
            "terms": {
            "terms": {"field": field_name, "size": 30},
            "aggs": {"products": {"reverse_nested": {}}},
            }
        },
    }


FACET_AGGS = {
    "brand": {"values": {"terms": {"field": "brand", "size": 30}}},
    "category": {"values": {"terms": {"field": "category", "size": 30}}},
    "color": {"values": _nested_variant_terms("variants.color")},
    "size": {"values": _nested_variant_terms("variants.size")},
    "price": {
    "values": {"range": {"field": "price", "ranges": PRICE_RANGES}},
    "stats": {"stats": {"field": "price"}}, # min/max for a price slider
    },
    "rating": {"values": {"range": {"field": "rating", "ranges": RATING_RANGES}}},
}


def build_aggs(p: SearchParams) -> dict:
    return {
        name: {"filter": {"bool": {"filter": filter_clauses(p, exclude=name)}}, "aggs": sub_aggs}
        for name, sub_aggs in FACET_AGGS.items()
    }


# ---------- full request ----------

def build_search_body(p: SearchParams) -> dict:
    if p.sort not in SORTS:
        raise ValueError(f"Unknown sort '{p.sort}'. Choose one of: {', '.join(SORTS)}")
    offset = (p.page - 1) * p.per_page
    if offset + p.per_page > MAX_RESULT_WINDOW:
        raise ValueError(f"Cannot page past {MAX_RESULT_WINDOW:,} results with from/size; use search_after")

    body: dict = {
        "query": build_query(p),
        "aggs": build_aggs(p),
        "sort": SORTS[p.sort],
        "from": offset,
        "size": p.per_page,
        "track_total_hits": True,
        "_source": SOURCE_FIELDS,
    }
    if selected := filter_clauses(p):
        body["post_filter"] = {"bool": {"filter": selected}}
    if p.q:
        body["highlight"] = {
            "pre_tags": ["<em>"],
            "post_tags": ["</em>"],
            "fields": {
                "name": {"number_of_fragments": 0}, # 0 = highlight the whole field
                "description": {"fragment_size": 150, "number_of_fragments": 1},
            },
        }
    return body
