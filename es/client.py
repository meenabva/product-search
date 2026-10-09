import os
from functools import lru_cache

from elasticsearch import Elasticsearch

@lru_cache
def get_client():
    return Elasticsearch(os.getenv("ES_URL", "http://localhost:9200"), request_timeout=30)