from tiktok_ads import brief_report


def test_heading_and_paragraph():
    out = brief_report.md_to_html("# Title\n\nSome text.")
    assert "<h1>Title</h1>" in out
    assert "<p>Some text.</p>" in out


def test_bulleted_list():
    out = brief_report.md_to_html("- one\n- two")
    assert "<ul>" in out
    assert out.count("<li>") == 2


def test_numbered_list_is_one_continuous_list():
    # The old converter restarted numbering per item, making ideas read as one.
    out = brief_report.md_to_html("1. first\n2. second")
    assert out.count("<ol>") == 1
    assert out.count("<li>") == 2


def test_nested_list_is_not_flattened():
    out = brief_report.md_to_html("1. Concept\n    - hook\n    - beat")
    assert "<ol>" in out and "<ul>" in out


def test_inline_bold():
    out = brief_report.md_to_html("A **bold** move")
    assert "<strong>bold</strong>" in out


def test_default_brief_pdf_path():
    assert brief_report.default_brief_pdf_path("output/x/brief.md") == "output/x/brief.pdf"
