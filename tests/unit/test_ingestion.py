from paperbrain.ingestion.inventory_csv import InventoryCsvParser, duplicate_reel_code_issues


def test_parser_rejects_ambiguous_width_unit() -> None:
    content = "reel_code,width,width_unit,gsm,length_mm\nR1,100,,250,100000\n"
    record = InventoryCsvParser().parse(content)[0]
    assert not record.executable
    assert any(issue.code == "UNIT_AMBIGUOUS" for issue in record.issues)


def test_duplicate_codes_are_reported() -> None:
    content = (
        "reel_code,width,width_unit,gsm,length_mm\n"
        "R1,1200,mm,250,100000\n"
        "R1,1300,mm,250,100000\n"
    )
    records = InventoryCsvParser().parse(content)
    issues = duplicate_reel_code_issues(records)
    assert 3 in issues
    assert issues[3].code == "DUPLICATE_REEL_CODE"
