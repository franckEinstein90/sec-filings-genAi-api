from sec_filings.rag.chunking import chunk_filing_text, split_text


def test_split_text_respects_chunk_size():
    text = ("alpha beta gamma. " * 80).strip()
    chunks = split_text(text, chunk_size=120, chunk_overlap=20)
    assert len(chunks) > 1
    assert all(len(chunk) <= 160 for chunk in chunks)


def test_item_headings_become_sections():
    text = """
Cover page and table of contents.

Item 1A. Risk Factors
We depend on a small number of suppliers.

Item 7. Management's Discussion and Analysis
Revenue increased year over year.
""".strip()
    chunks = chunk_filing_text(text, chunk_size=400, chunk_overlap=20)
    sections = {chunk.section for chunk in chunks}
    assert any(section and section.startswith("Item 1A") for section in sections)
    assert any(section and section.startswith("Item 7") for section in sections)
