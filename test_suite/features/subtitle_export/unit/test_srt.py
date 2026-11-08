import pysubs2

from app.infrastructure.media.subtitle_files import write_srt


def test_srt_roundtrip_unicode_timestamps_and_literal_braces(tmp_path):
    path = tmp_path / "lesson.srt"
    cues = [
        (0.125, 1.999, "adapt /əˈdæpt/ — thích nghi"),
        (2.0, 4.001, "Although {clause}, another clause."),
    ]
    write_srt(path, cues)
    text = path.read_text()
    assert "00:00:00,125 --> 00:00:01,999" in text
    assert "{clause}" in text
    parsed = pysubs2.load(str(path), encoding="utf-8", format_="srt", keep_html_tags=True)
    assert parsed[0].plaintext == cues[0][2]
    assert parsed[1].start == 2000 and parsed[1].end == 4001


def test_literal_ass_sequences_do_not_change_lesson_text(tmp_path):
    path = tmp_path / "grammar.srt"
    text = r"Use C:\New, \n and \h literally."
    write_srt(path, [(0, 1, text)])
    assert text in path.read_text()
    assert "C:\n" not in path.read_text()
