from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_legacy_domain_terms_are_gone():
    forbidden = (
        "collective bargaining",
        "collective_bargaining",
        "union_steward",
        "steward_rag",
        "upload_cba",
        "query_cba",
        "faiss",
    )
    hits = []
    for path in ROOT.rglob("*"):
        if ".git" in path.parts or path.suffix not in {".py", ".md", ".txt", ".yml", ".yaml", ".ini"}:
            continue
        if path.name == "test_no_legacy_domain.py":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for term in forbidden:
            if term in text:
                hits.append(f"{path.relative_to(ROOT)}: {term}")
    assert hits == []
