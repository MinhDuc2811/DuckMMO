import pytest
from pydantic import ValidationError

from app.contracts.speech import speech_segments
from app.schemas import RenderOptions


def test_continuous_script_is_one_utterance_not_subtitle_sized():
    script = ("Một câu chuyện tiếng Việt cần được đọc tự nhiên và liền mạch " * 16).strip()
    assert len(script) > 105
    assert speech_segments(script) == [script]


def test_long_scripts_preserve_words_punctuation_and_limit():
    script = "Câu đầu tiên rất ngắn. " + ("Nội dung dài, tiếp nối tự nhiên; không mất từ. " * 200)
    parts = speech_segments(script)
    assert len(parts) > 1
    assert all(0 < len(part) <= 2500 for part in parts)
    assert " ".join(parts).split() == script.split()
    assert speech_segments("") == []
    assert speech_segments("A" * 5001) == ["A" * 2500, "A" * 2500, "A"]


def test_edge_escaped_utf8_budget_keeps_vietnamese_and_xml_safe():
    from xml.sax.saxutils import escape

    text = ("Tiếng Việt & những câu chuyện <mới> được kể tự nhiên. " * 200).strip()
    parts = speech_segments(text, max_bytes=3500)
    assert len(parts) > 1
    assert all(len(escape(part).encode("utf-8")) <= 3500 for part in parts)
    assert " ".join(parts).split() == text.split()


def test_paid_voice_ids_are_rejected():
    with pytest.raises(ValidationError):
        RenderOptions(expected_content_hash="0" * 64, voice="fpt:banmai")


def test_edge_websocket_uses_existing_https_proxy(monkeypatch):
    from app.infrastructure.media import speech

    monkeypatch.setattr(speech, "getproxies", lambda: {"https": "http://proxy.fixture:8080"})
    monkeypatch.setattr(speech, "proxy_bypass", lambda _: False)
    assert speech.edge_proxy() == "http://proxy.fixture:8080"


def test_edge_websocket_respects_no_proxy_and_wss_override(monkeypatch):
    from app.infrastructure.media import speech

    monkeypatch.setattr(
        speech,
        "getproxies",
        lambda: {
            "https": "http://https-proxy.fixture:8080",
            "wss": "http://ws-proxy.fixture:8080",
        },
    )
    monkeypatch.setattr(speech, "proxy_bypass", lambda _: False)
    assert speech.edge_proxy() == "http://ws-proxy.fixture:8080"
    monkeypatch.setattr(speech, "proxy_bypass", lambda _: True)
    assert speech.edge_proxy() is None
