"""Tiny pure-stdlib TF-IDF index over the markdown policy library."""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for",
    "from", "how", "i", "if", "in", "is", "it", "many", "my", "of", "on", "or",
    "should", "the", "to", "what", "when", "where", "which", "who", "with", "you",
}

TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS and len(t) > 1]


def load_sections(policies_dir: Path) -> list[dict]:
    sections = []
    for path in sorted(policies_dir.glob("*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        title = next((l.lstrip("# ").strip() for l in lines if l.startswith("# ")), path.stem)
        heading, buf = None, []
        for line in lines:
            if line.startswith("## "):
                if heading and buf:
                    sections.append(_section(path.name, title, heading, buf))
                heading, buf = line.lstrip("# ").strip(), []
            elif not line.startswith("# "):
                buf.append(line)
        if heading and buf:
            sections.append(_section(path.name, title, heading, buf))
    return sections


def _section(source: str, doc_title: str, heading: str, lines: list[str]) -> dict:
    text = re.sub(r"\s+", " ", " ".join(lines)).strip()
    return {"source": source, "doc_title": doc_title, "heading": heading, "text": text}


class PolicyIndex:
    def __init__(self, sections: list[dict]):
        self.sections = sections
        self.df: Counter = Counter()
        self.vectors: list[dict[str, float]] = []
        for s in sections:
            tf = Counter(tokenize(f"{s['heading']} {s['text']} {s['heading']}"))
            for term in tf:
                self.df[term] += 1
            self.vectors.append(tf)
        n = len(sections)
        self.idf = {t: math.log((n + 1) / (c + 1)) + 1 for t, c in self.df.items()}
        self.vectors = [self._weigh(tf) for tf in self.vectors]

    def _weigh(self, tf: Counter) -> dict[str, float]:
        vec = {t: (1 + math.log(c)) * self.idf.get(t, 1.0) for t, c in tf.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norm for t, v in vec.items()}

    def search(self, query: str, k: int = 3) -> list[tuple[float, dict]]:
        qvec = self._weigh(Counter(tokenize(query)))
        scored = []
        for vec, section in zip(self.vectors, self.sections):
            score = sum(w * vec.get(t, 0.0) for t, w in qvec.items())
            if score > 0:
                scored.append((round(score, 4), section))
        scored.sort(key=lambda x: -x[0])
        return scored[:k]

    @classmethod
    def build(cls, policies_dir: Path) -> "PolicyIndex":
        return cls(load_sections(policies_dir))

    def save(self, path: Path) -> None:
        payload = {
            "sections": self.sections,
            "df": self.df,
            "vectors": self.vectors,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "PolicyIndex":
        payload = json.loads(path.read_text(encoding="utf-8"))
        idx = cls(payload["sections"])
        idx.df = Counter(payload["df"])
        idx.vectors = payload["vectors"]
        return idx


def citation(section: dict) -> str:
    return f"{section['source']} § {section['heading']}"
