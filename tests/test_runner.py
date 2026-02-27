from src.agents.runner import extract_json_from_messages

def test_extract_json_from_text():
    """テキスト中のJSONブロックを抽出できる"""
    text = 'Here is the analysis:\n```json\n{"analyst":"bloodline","race_id":"test","analysis":"test","rankings":[],"confidence":0.5,"warnings":[]}\n```'
    result = extract_json_from_messages(text)
    assert result["analyst"] == "bloodline"

def test_extract_json_bare():
    """JSONが直接返された場合も抽出できる"""
    text = '{"analyst":"bloodline","race_id":"test","analysis":"test","rankings":[],"confidence":0.5,"warnings":[]}'
    result = extract_json_from_messages(text)
    assert result["analyst"] == "bloodline"

def test_extract_json_not_found():
    """JSONが見つからない場合はNoneを返す"""
    result = extract_json_from_messages("No JSON here")
    assert result is None
