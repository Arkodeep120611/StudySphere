"""Select the parts of a document that fit inside the model's context budget."""

import re

CHUNK_SIZE = 2000
_STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "any", "can", "what", "when",
    "where", "which", "who", "how", "why", "with", "this", "that", "from", "have", "has",
    "was", "were", "will", "would", "could", "should", "there", "their", "they", "them",
    "about", "into", "your", "explain", "tell", "give", "show", "does", "is", "it", "of",
    "to", "in", "on", "a", "an", "be", "or", "as", "at", "by", "me", "my",
}
_SUMMARY_HINT = re.compile(r"\b(summari[sz]e|summary|overview|outline|main points|key points|tl;?dr)\b")


def is_summary_request(message: str) -> bool:
    return bool(_SUMMARY_HINT.search(message.lower()))


def build_context(text: str, max_chars: int, focus: str | None = None) -> str:
    """Return up to ``max_chars`` of ``text``.

    Short documents are returned whole. Longer ones are sampled: evenly across the
    document when no focus is given (for generation and summaries), or by keyword
    overlap with ``focus`` (for specific questions). Selected chunks keep their order.
    """
    if len(text) <= max_chars:
        return text

    chunks = [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]
    slots = max(1, max_chars // CHUNK_SIZE)

    if focus and not is_summary_request(focus):
        terms = {
            word for word in re.findall(r"[a-z]{3,}", focus.lower()) if word not in _STOPWORDS
        }
        if terms:
            scored = []
            for index, chunk in enumerate(chunks):
                lowered = chunk.lower()
                score = sum(lowered.count(term) for term in terms)
                scored.append((score, index))
            # Highest scores first, earliest chunk breaks ties.
            ranked = sorted(scored, key=lambda item: (-item[0], item[1]))
            picked = sorted(index for score, index in ranked[:slots] if score > 0)
            if picked:
                return _join(chunks, picked, max_chars)

    if len(chunks) <= slots:
        picked = list(range(len(chunks)))
    else:
        step = len(chunks) / slots
        picked = sorted({int(i * step) for i in range(slots)})
    return _join(chunks, picked, max_chars)


_SEPARATOR = "\n\n...\n\n"


def _join(chunks, indexes, max_chars):
    pieces, used = [], 0
    for index in indexes:
        chunk = chunks[index]
        cost = len(chunk) + (len(_SEPARATOR) if pieces else 0)
        if used + cost > max_chars:
            break
        pieces.append(chunk)
        used += cost
    return _SEPARATOR.join(pieces)
