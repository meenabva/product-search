"""FastAPI app. Run from the project root:

uvicorn api.main:app --reload

then open http://localhost:8000/docs for an interactive UI.
"""
from typing import Annotated, Literal

from elasticsearch import NotFoundError
from fastapi import FastAPI, HTTPException, Query

from es.client import get_client
from search import service
from search.query_builder import SearchParams

app = FastAPI(title="E-commerce Product Search", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"elasticsearch": get_client().cluster.health()["status"]}


@app.get("/search")
def search(
    q: Annotated[str | None, Query(description="Full-text query, e.g. 'noise cancelling headphones'")] = None,
    brand: Annotated[list[str], Query(description="Repeat for OR: ?brand=Apple&brand=Samsung")] = [],
    category: Annotated[list[str], Query()] = [],
    color: Annotated[list[str], Query()] = [],
    size: Annotated[list[str], Query()] = [],
    price_min: Annotated[float | None, Query(ge=0)] = None,
    price_max: Annotated[float | None, Query(ge=0)] = None,
    min_rating: Annotated[float | None, Query(ge=0, le=5)] = None,
    in_stock_only: bool = False,
    sort: Literal["relevance", "price_asc", "price_desc", "rating", "newest"] = "relevance",
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    debug: Annotated[bool, Query(description="Include the generated Elasticsearch request")] = False,
) -> dict:
    params = SearchParams(
    q=q.strip() if q and q.strip() else None,
    brand=brand, category=category, color=color, size=size,
    price_min=price_min, price_max=price_max, min_rating=min_rating,
    in_stock_only=in_stock_only, sort=sort, page=page, per_page=per_page,
    )
    try:
        return service.search(get_client(), params, debug=debug)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/product/{product_id}")
def product(product_id: str) -> dict:
    try:
        return service.get_product(get_client(), product_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")


@app.get("/analyze")
def analyze(
    text: str,
    analyzer: Literal["product_text", "product_search", "autocomplete", "standard"] = "product_search",
) -> dict:
    return {"analyzer": analyzer, "tokens": service.analyze(get_client(), text, analyzer)}
