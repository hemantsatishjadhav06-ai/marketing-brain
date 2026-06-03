"""External data sources (Phase 2): trends, SerpAPI, YouTube, competitors.

Each must be cached in Postgres with TTL behind a single `data_sources`
abstraction; degrade gracefully if a source is down (spec § 9).
"""
