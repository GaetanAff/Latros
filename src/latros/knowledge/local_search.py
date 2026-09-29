"""Transparent, offline BM25 on temporary search designations (not medical evidence)."""

from __future__ import annotations

from typing import Any, Literal

import duckdb

SearchMode = Literal["bm25", "bm25_fuzzy"]

# A negative sentence must not be reinterpreted as a PRESENT observation.
# These are UI safety guards, not a clinical negation extractor.
NEGATION_TOKENS = frozenset(
    {
        "pas",
        "sans",
        "aucun",
        "aucune",
        "absence",
        "nicht",
        "kein",
        "keine",
        "keinen",
        "no",
        "not",
        "without",
    }
)
FILLER_TOKENS = frozenset(
    {
        "je",
        "j",
        "ai",
        "me",
        "mon",
        "ma",
        "mes",
        "le",
        "la",
        "les",
        "de",
        "des",
        "du",
        "au",
        "aux",
        "a",
        "est",
        "il",
        "qui",
        "quand",
        "ich",
        "mir",
        "ist",
        "beim",
        "der",
        "die",
        "das",
        "und",
        "the",
        "an",
        "my",
        "when",
        "i",
        "have",
    }
)


def meaningful_tokens(normalized: str) -> list[str]:
    tokens = normalized.split()[:10]
    if any(token in NEGATION_TOKENS for token in tokens):
        return []
    return [token for token in tokens if token not in FILLER_TOKENS and len(token) >= 2]


def prepare_bm25(connection: duckdb.DuckDBPyConnection) -> None:
    """Derived temporary FTS-like index; no DuckDB INSTALL or snapshot mutation."""
    connection.execute(
        "CREATE OR REPLACE TEMP TABLE ui_search_documents AS "
        "SELECT row_number() OVER() AS doc_id,concept_id,language,normalized,scope, "
        "greatest(1,array_length(string_split(normalized,' '))) AS doc_length "
        "FROM ui_search_terms WHERE normalized!=''"
    )
    connection.execute(
        "CREATE OR REPLACE TEMP TABLE ui_search_tokens AS "
        "SELECT d.doc_id,d.concept_id,d.language,d.normalized,d.scope,d.doc_length,t.token "
        "FROM ui_search_documents d,UNNEST(string_split(d.normalized,' ')) AS t(token) "
        "WHERE length(t.token)>=2"
    )
    connection.execute(
        "CREATE OR REPLACE TEMP TABLE ui_search_token_stats AS "
        "SELECT language,token,count(DISTINCT doc_id) AS df FROM ui_search_tokens "
        "GROUP BY language,token"
    )
    connection.execute(
        "CREATE OR REPLACE TEMP TABLE ui_search_corpus_stats AS "
        "SELECT language,count(*) AS n,avg(doc_length) AS avgdl "
        "FROM ui_search_documents GROUP BY language"
    )


def ranked_ids(
    connection: duckdb.DuckDBPyConnection,
    normalized: str,
    language: str,
    limit: int,
    mode: SearchMode,
) -> list[tuple[str, int]]:
    tokens = meaningful_tokens(normalized)
    if not tokens:
        return []
    # All informative tokens must co-occur in one designation/alias, never by
    # joining unrelated names of a concept. Exact/alias matches outrank BM25.
    # Single-edit fuzzy is public-lexicon-only and survives only one target.
    sql = (
        "WITH lexical AS (SELECT t.concept_id,t.doc_id,t.scope,t.normalized, "
        "sum(ln(1+(s.n-f.df+0.5)/(f.df+0.5))*2.2/"
        "(1+1.2*(0.25+0.75*t.doc_length/s.avgdl))) AS bm25, "
        "count(DISTINCT t.token) AS matched "
        "FROM ui_search_tokens t "
        "JOIN ui_search_token_stats f ON f.language=t.language AND f.token=t.token "
        "JOIN ui_search_corpus_stats s ON s.language=t.language "
        "WHERE t.language=? AND t.token IN (SELECT unnest(?::VARCHAR[])) "
        "GROUP BY t.concept_id,t.doc_id,t.scope,t.normalized "
        "HAVING matched=?), "
        "local AS (SELECT concept_id, "
        "CASE WHEN normalized=? AND scope IN ('preferred','ui_preferred') THEN 0 "
        "WHEN normalized=? THEN 1 WHEN starts_with(normalized,?) THEN 2 "
        "ELSE 3 END AS rank, max(bm25) AS bm25 FROM lexical "
        "GROUP BY concept_id,normalized,scope), "
        "prefix AS (SELECT DISTINCT concept_id,2 AS rank,0.0 AS bm25 "
        "FROM ui_search_terms WHERE language=? AND starts_with(normalized,?)), "
        "english AS (SELECT DISTINCT concept_id,5 AS rank,0.0 AS bm25 "
        "FROM ui_search_terms WHERE language='en' AND "
        "(normalized=? OR starts_with(normalized,?))), "
        "fuzzy AS (SELECT DISTINCT concept_id,4 AS rank,0.0 AS bm25 "
        "FROM ui_search_terms WHERE language=? AND scope IN ('ui_alias','ui_preferred') "
        "AND length(?)>=5 AND levenshtein(normalized,?)=1), "
        "safe_fuzzy AS (SELECT * FROM fuzzy WHERE "
        "(SELECT count(DISTINCT concept_id) FROM fuzzy)=1), "
        "combined AS (SELECT * FROM local UNION ALL SELECT * FROM prefix "
        "UNION ALL SELECT * FROM english "
    )
    if mode == "bm25_fuzzy":
        sql += "UNION ALL SELECT * FROM safe_fuzzy "
    sql += (
        "), best AS (SELECT concept_id,min(rank) AS rank,max(bm25) AS bm25 "
        "FROM combined GROUP BY concept_id) "
        "SELECT o.concept_id,b.rank FROM best b "
        "JOIN ui_observations o USING(concept_id) "
        "ORDER BY b.rank,b.bm25 DESC,lower(o.label),o.code,o.concept_id LIMIT ?"
    )
    parameters: list[Any] = [
        language,
        tokens,
        len(set(tokens)),
        normalized,
        normalized,
        normalized,
        language,
        normalized,
        normalized,
        normalized,
        language,
        normalized,
        normalized,
        limit,
    ]
    return [(str(row[0]), int(row[1])) for row in connection.execute(sql, parameters).fetchall()]
