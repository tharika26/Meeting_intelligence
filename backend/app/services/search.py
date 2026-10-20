"""
Semantic-ish search across past meetings.

Uses TF-IDF + cosine similarity over each meeting's (summary + transcript +
decisions + actions) text. This is fully offline (no model download / API
key required), fast, and gives strong relevance for keyword and paraphrase
style queries typical of meeting search ("what did we decide about the
vendor", "action items for Ananya").

To upgrade to true dense-vector semantic search in production, swap
`_vectorize()` for an embeddings call (e.g. Anthropic/OpenAI/local
sentence-transformers) - the rest of the ranking logic is unchanged.
"""
from __future__ import annotations

from typing import List, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.models import Meeting


def _document_for_meeting(m: Meeting) -> str:
    parts = [m.title or "", m.summary or ""]
    if m.transcript:
        parts.append(m.transcript.full_text or "")
    parts.extend(d.description for d in m.decisions)
    parts.extend(a.description for a in m.actions)
    parts.extend(r.description for r in m.risks)
    return "\n".join(p for p in parts if p)


def search_meetings(query: str, meetings: List[Meeting], top_k: int = 5) -> List[Tuple[Meeting, float, str]]:
    """Returns list of (meeting, score, snippet) sorted by relevance desc."""
    candidates = [m for m in meetings if _document_for_meeting(m).strip()]
    if not candidates or not query.strip():
        return []

    docs = [_document_for_meeting(m) for m in candidates]
    vectorizer = TfidfVectorizer(stop_words="english", max_features=20000)
    try:
        doc_matrix = vectorizer.fit_transform(docs + [query])
    except ValueError:
        return []  # e.g. query is only stopwords

    query_vec = doc_matrix[-1]
    doc_vecs = doc_matrix[:-1]
    scores = cosine_similarity(query_vec, doc_vecs).flatten()

    ranked = sorted(zip(candidates, scores, docs), key=lambda x: x[1], reverse=True)
    ranked = [r for r in ranked if r[1] > 0][:top_k]

    results = []
    for meeting, score, doc in ranked:
        snippet = _make_snippet(doc, query)
        results.append((meeting, float(score), snippet))
    return results


def _make_snippet(doc: str, query: str, window: int = 160) -> str:
    lower_doc = doc.lower()
    for term in query.lower().split():
        idx = lower_doc.find(term)
        if idx != -1:
            start = max(0, idx - window // 2)
            end = min(len(doc), idx + window // 2)
            snippet = doc[start:end].strip().replace("\n", " ")
            return ("..." if start > 0 else "") + snippet + ("..." if end < len(doc) else "")
    return doc[:window].replace("\n", " ") + ("..." if len(doc) > window else "")
