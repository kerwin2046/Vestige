from crawlers.extractors import extract_json_ld, extract_opengraph


def test_extract_json_ld_parses_script_blocks():
    html = """
    <html><head>
    <script type="application/ld+json">
    {"@type": "Organization", "name": "Acme"}
    </script>
  </head></html>
    """
    items = extract_json_ld(html)
    assert len(items) == 1
    assert items[0]["@type"] == "Organization"


def test_extract_opengraph_reads_meta_tags():
    html = '<meta property="og:title" content="Acme Inc" />'
    og = extract_opengraph(html)
    assert og["title"] == "Acme Inc"
