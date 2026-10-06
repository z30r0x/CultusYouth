from datetime import date

from fetch_opportunities import (build_record, clean_text, extract_deadline, extract_link,
                                 extract_name, label, safe_url)

TODAY = date(2026, 10, 4)
POST = """🔥 فرصة: برنامج تدريب صيفي في الذكاء الاصطناعي
📍 عن بعد
⏰ آخر موعد للتقديم: ١٥ أكتوبر ٢٠٢٦
رابط التقديم: https://example.com/apply
#internship"""


def test_arabic_deadline_text_and_digits():
    assert extract_deadline(POST, TODAY) == "2026-10-15"


def test_numeric_deadline_dd_mm():
    assert extract_deadline("Deadline: 20/11/2026", TODAY) == "2026-11-20"
    assert extract_deadline("آخر موعد ٣١-١٢", TODAY) == "2026-12-31"


def test_deadline_missing():
    assert extract_deadline("no dates here", TODAY) is None


def test_name_strips_emoji_and_prefix():
    assert extract_name(POST) == "برنامج تدريب صيفي في الذكاء الاصطناعي"


def test_link_prefers_apply_and_skips_telegram():
    links = ["https://t.me/foo", "https://other.com", "https://example.com/apply"]
    assert extract_link(links, POST) == "https://example.com/apply"


def test_labels():
    tracks, mode, otype = label(POST)
    assert tracks == ["ai"] and mode == "remote" and otype == "internship"


def test_default_type_used_when_no_keyword():
    assert label("some post about stuff", default_type="scholarship")[2] == "scholarship"


def test_sanitization():
    assert "<" not in clean_text("<script>alert(1)</script>Hello &lt;b&gt;")
    assert safe_url("javascript:alert(1)") is None
    assert safe_url("data:text/html,x") is None
    assert safe_url("https://ok.com/x") == "https://ok.com/x"


def test_record_flags_review_when_incomplete():
    rec = build_record({"post_id": "g/1", "source_url": None, "posted_at": None,
                        "text": "ورشة عن الويب", "links": []}, TODAY)
    assert rec["type"] == "workshop" and rec["needs_review"] is True


# ---------------- approval flow ----------------
import json

import fetch_opportunities as fo


def _rec(i, name="x"):
    return {"id": f"g/{i}", "short_id": fo.short_id(f"g/{i}"), "name": name, "deadline": "2026-10-15",
            "apply_url": "https://a.com", "tracks": ["ai"], "mode": "remote", "type": "internship",
            "posted_at": "2026-10-01", "source_url": None, "needs_review": False, "emailed": True}


def test_email_body_has_ids_and_commands():
    body = fo.format_email_body([_rec(1, "Intern at X")])
    assert fo.short_id("g/1") in body and "--approve" in body and "Intern at X" in body


def test_approve_and_reject(tmp_path, monkeypatch):
    monkeypatch.setattr(fo, "PENDING", tmp_path / "p.json")
    monkeypatch.setattr(fo, "OUTPUT", tmp_path / "o.json")
    monkeypatch.setattr(fo, "REJECTED", tmp_path / "r.json")
    fo._save(fo.PENDING, [_rec(1), _rec(2)])
    fo.resolve([fo.short_id("g/1")], approve=True)
    fo.resolve([fo.short_id("g/2")], approve=False)
    out = json.loads(fo.OUTPUT.read_text(encoding="utf-8"))
    assert [o["id"] for o in out] == ["g/1"] and "short_id" not in out[0] and "emailed" not in out[0]
    assert json.loads(fo.REJECTED.read_text()) == ["g/2"] and json.loads(fo.PENDING.read_text()) == []


def test_unconfigured_email_keeps_pending(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(fo, "PENDING", tmp_path / "p.json")
    for k in ("SMTP_HOST", "SMTP_USER", "SMTP_APP_PASSWORD", "EMAIL_TO"):
        monkeypatch.delenv(k, raising=False)
    r = _rec(1); r["emailed"] = False
    fo._save(fo.PENDING, [r])
    fo.notify_pending()
    assert "not configured" in capsys.readouterr().out
    assert json.loads(fo.PENDING.read_text())[0]["emailed"] is False
