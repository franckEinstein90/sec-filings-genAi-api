import pytest

from sec_filings.db.models import Filing
from sec_filings.edgar.extract import FilingExtractionError, extract_text


def test_corrupt_pdf_raises_domain_extraction_error():
    with pytest.raises(FilingExtractionError, match="Unable to parse PDF filing"):
        extract_text(b"%PDF-1.7\nthis is not a valid pdf", filename="broken.pdf")


def test_malformed_pdf_upload_returns_422_and_records_failure(client, fake_edgar, db_session):
    response = client.post(
        "/api/v1/filings/upload",
        data={"ticker": "MSFT", "form_type": "10-Q"},
        files={
            "file": (
                "malformed-test.pdf",
                b"%PDF-1.7\nnot really a pdf",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 422
    assert "parse PDF" in response.json()["detail"]

    filing = (
        db_session.query(Filing)
        .filter_by(title="malformed-test.pdf")
        .order_by(Filing.id.desc())
        .first()
    )
    assert filing is not None
    assert filing.processing_status == "failed"
    assert "parse PDF" in (filing.processing_error or "")
    assert filing.chunk_count == 0


def test_text_payload_with_no_extractable_content_returns_422(client, fake_edgar):
    response = client.post(
        "/api/v1/filings/upload",
        data={"ticker": "MSFT", "form_type": "8-K"},
        files={"file": ("empty-ish.txt", b"\x00\x01\x02\x03", "text/plain")},
    )

    assert response.status_code == 422
    assert "No extractable text" in response.json()["detail"]
