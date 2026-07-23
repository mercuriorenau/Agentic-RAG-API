from app.services.document_names import display_document_name, sanitize_upload_filename


def test_sanitize_upload_filename_strips_paths() -> None:
    assert sanitize_upload_filename("../../evil/policy.pdf") == "policy.pdf"
    assert sanitize_upload_filename(None) == "upload"


def test_display_document_name_keeps_human_names() -> None:
    assert display_document_name("Casos Lidl.pdf") == "Casos Lidl.pdf"


def test_display_document_name_rewrites_bare_uuid() -> None:
    name = "a3f2c1b0-1234-5678-9abc-def012345678.pdf"
    assert display_document_name(name) == "Uploaded PDF"
    assert display_document_name("a3f2c1b0-1234-5678-9abc-def012345678.txt") == "Uploaded text"
