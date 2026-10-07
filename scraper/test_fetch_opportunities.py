import json
from datetime import date

import fetch_opportunities as fo

TODAY = date(2026, 10, 4)
POST = """🔥 فرصة جديدة!
برنامج تدريب صيفي في الذكاء الاصطناعي من شركة X
📍 عن بعد
⏰ آخر موعد للتقديم: ١٥ أكتوبر ٢٠٢٦
رابط التقديم: https://example.com/apply
#internship"""


def test_deadline_arabic_and_numeric():
    assert fo.extract_deadline(POST, TODAY) == "2026-10-15"
    assert fo.extract_deadline("Deadline: 20/11/2026", TODAY) == "2026-11-20"
    assert fo.extract_deadline("آخر موعد ٣١-١٢", TODAY) == "2026-12-31"
    assert fo.extract_deadline("no dates", TODAY) is None


def test_title_skips_generic_header_and_is_tiny():
    assert fo.extract_title(POST).startswith("برنامج تدريب صيفي")
    long = fo.extract_title("برنامج " + "كلمة " * 40)
    assert len(long) <= fo.TITLE_LEN + 1 and long.endswith("…")
    assert fo.extract_title("فرصة: منحة الدراسة في ألمانيا") == "منحة الدراسة في ألمانيا"


def test_link_prefers_apply_and_skips_telegram():
    links = ["https://t.me/foo", "https://other.com", "https://example.com/apply"]
    assert fo.extract_link(links, POST) == "https://example.com/apply"


def test_labels_and_record():
    rec = fo.build_record({"post_id": "g/1", "source_url": None, "posted_at": "2026-10-01", "text": POST,
                           "links": ["https://example.com/apply"]}, TODAY)
    assert (rec["tracks"], rec["mode"], rec["type"]) == (["ai"], "remote", "internship")
    assert rec["deadline"] == "2026-10-15" and rec["needs_review"] is False


def test_sanitization():
    assert "<" not in fo.clean_text("<script>alert(1)</script>Hello &lt;b&gt;")
    assert fo.safe_url("javascript:alert(1)") is None and fo.safe_url("https://ok.com/x")


def test_year_and_expiry_filters():
    assert fo.in_year({"posted_at": "2025-12-20T10:00:00+00:00", "deadline": "2026-01-10"}, 2026)
    assert not fo.in_year({"posted_at": "2025-05-01T10:00:00+00:00", "deadline": "2025-06-01"}, 2026)
    assert fo.is_expired({"deadline": "2026-10-01"}, TODAY) and not fo.is_expired({"deadline": None}, TODAY)


def _rec(i, name="x"):
    return {"id": f"g/{i}", "short_id": fo.short_id(f"g/{i}"), "name": name, "deadline": "2026-10-15",
            "apply_url": "https://a.com", "tracks": ["ai"], "mode": "remote", "type": "internship",
            "posted_at": "2026-10-01", "source_url": None, "needs_review": False, "emailed": True}


def _paths(tmp_path, monkeypatch):
    for n, f in (("PENDING", "p"), ("OUTPUT", "o"), ("REJECTED", "r")):
        monkeypatch.setattr(fo, n, tmp_path / f"{f}.json")


def test_email_is_a_numbered_list():
    body = fo.format_email_body([_rec(1, "Intern at X"), _rec(2, "Second")], TODAY)
    assert "1. [" in body and "2. [" in body and "--review" in body and "Intern at X" in body and "in 11 days" in body


def test_resolve_by_id(tmp_path, monkeypatch):
    _paths(tmp_path, monkeypatch)
    fo._save(fo.PENDING, [_rec(1), _rec(2)])
    fo.resolve([fo.short_id("g/1")], True)
    fo.resolve([fo.short_id("g/2")], False)
    out = json.loads(fo.OUTPUT.read_text(encoding="utf-8"))
    assert [o["id"] for o in out] == ["g/1"] and "short_id" not in out[0] and "emailed" not in out[0]
    assert json.loads(fo.REJECTED.read_text()) == ["g/2"] and json.loads(fo.PENDING.read_text()) == []


def test_review_one_by_one_with_edit(tmp_path, monkeypatch):
    _paths(tmp_path, monkeypatch)
    fo._save(fo.PENDING, [_rec(1, "First"), _rec(2, "Second"), _rec(3, "Third"), _rec(4, "Fourth")])
    # 1: edit title+deadline+link then approve | 2: reject | 3: skip | 4: quit
    answers = iter(["e", "Better title", "2026-12-01", "https://new.com", "a", "r", "s", "q"])
    monkeypatch.setattr("builtins.input", lambda _="": next(answers))
    fo.review()
    out = json.loads(fo.OUTPUT.read_text(encoding="utf-8"))
    assert out[0]["name"] == "Better title" and out[0]["deadline"] == "2026-12-01" and out[0]["apply_url"] == "https://new.com"
    assert json.loads(fo.REJECTED.read_text()) == ["g/2"]
    assert [r["id"] for r in json.loads(fo.PENDING.read_text())] == ["g/3", "g/4"]


def test_edit_rejects_bad_input(monkeypatch):
    r = _rec(1)
    answers = iter(["", "not-a-date", "javascript:alert(1)"])
    monkeypatch.setattr("builtins.input", lambda _="": next(answers))
    fo._edit(r)
    assert r["deadline"] == "2026-10-15" and r["apply_url"] == "https://a.com"


def test_unconfigured_email_keeps_pending(tmp_path, monkeypatch, capsys):
    _paths(tmp_path, monkeypatch)
    for k in ("SMTP_HOST", "SMTP_USER", "SMTP_APP_PASSWORD", "EMAIL_TO"):
        monkeypatch.delenv(k, raising=False)
    r = _rec(1)
    r["emailed"] = False
    fo._save(fo.PENDING, [r])
    fo.notify_pending()
    assert "not configured" in capsys.readouterr().out
    assert json.loads(fo.PENDING.read_text())[0]["emailed"] is False