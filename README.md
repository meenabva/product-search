# Product Search (Elasticsearch playground)

Phases 1–4: setup and data, index design, full-text search, faceted navigation.

```
docker-compose.yml Elasticsearch 8.15 + Kibana (single node, security off)
data/generate_products.py 10k realistic products -> data/products.jsonl (stdlib only)
es/mappings.py analyzers (stemming, synonyms, edge n-gram) + mappings
es/synonyms.txt search-time synonyms
es/setup.py versioned index (products_v1) + bulk load + alias "products"
search/query_builder.py pure DSL builders: full-text, boosts, facets, sort, paging
search/service.py runs searches, formats hits and facets
api/main.py FastAPI: /search, /product/{id}, /analyze, /health
```

## Run

```bash
docker compose up -d # wait ~30s; check http://localhost:9200
uv sync
uv run python -m data.generate_products # already generated; re-run to change --count/--seed
uv run python -m es.setup --recreate
uv run uvicorn api.main:app --reload # http://localhost:8000/docs
```

Kibana Dev Tools is at http://localhost:5601/app/dev_tools#/console.

## Try these

| What | URL |
|---|---|
| Full-text + highlighting | `/search?q=noise cancelling headphones` |
| Typo tolerance | `/search?q=iphnoe` |
| Synonyms (tv → television) | `/search?q=television 55 inch` |
| Browse (popularity ranking) | `/search` |
| Multi-select facets (OR within, AND across) | `/search?q=shoes&brand=Nike&brand=Adidas&size=UK 9` |
| Price + rating filters, sort | `/search?category=Laptops&price_max=80000&min_rating=4&sort=price_asc` |
| Same-variant match (nested) | `/search?category=Mobiles&color=black&size=512GB` |
| See the generated ES query | add `&debug=true` |
| Inspect analyzers | `/analyze?text=Running shoes for TV lovers&analyzer=product_search` |

## Experiments

1. **Facets that don't hide their own options.** Select `brand=Apple`. The brand facet still
shows Samsung, Sony and the others, because selected values live in `post_filter` and each facet
excludes its own filter. Move the filters into `query` to see the difference.
2. **Scoring.** Run the `es_request` from `debug=true` in Kibana with `"explain": true`.
Change the boosts in `with_business_boosts()` or the `name^3` field weight and compare.
3. **Analyzers.** Compare `/analyze` output for `product_text` and `product_search` (synonyms
are added only at search time). Try `autocomplete` to see edge n-grams.
4. **Synonyms.** Edit `es/synonyms.txt` and rebuild with `--recreate`. Search analyzers can
change without reindexing, but inline synonyms still need the index closed and reopened.
5. **Zero-downtime reindex.** Change a mapping, run `python -m es.setup --version 2`, and
the alias swaps atomically. Delete `products_v1` afterwards.
6. **Pagination limits.** `page=600` returns 400 (the 10k window). Implement `search_after` + PIT.
7. **Nested vs flat.** Map `variants` as a plain `object` and see `color=black&size=512GB`
match products where black and 512GB come from *different* variants.

## Next phases

The data already includes `stores[].location` for geo search (Phase 7), and the mapping has
`name.suggest` / `name.ngram` for autocomplete (Phase 5).
