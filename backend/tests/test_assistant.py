from datetime import datetime, timezone

import httpx

from app.services.assistant.gemini import GeminiClient, GeminiError
from app.services.assistant.search import SearchFilter, rule_based_filter
from app.services.assistant.service import Assistant
from app.labels import Label

NOW = datetime(2026, 11, 5, 15, 0, tzinfo=timezone.utc)
STATS = {"total": 10, "por_rotulo": {"LIMPO": 8, "SEVERO": 2}, "para_revisao": 1, "limpezas_acionadas": 4}


class Fake:
    def __init__(self, json_obj=None, text="", boom=False):
        self.json_obj, self.text, self.boom = json_obj, text, boom

    def generate_json(self, *a, **k):
        if self.boom: raise GeminiError("x")
        return self.json_obj

    def generate(self, *a, **k):
        if self.boom: raise GeminiError("x")
        return self.text


def test_rules():
    f = rule_based_filter("mostre as fotos sujas de hoje para revisar", NOW)
    assert f.labels == [Label.SEVERO] and f.since and f.needs_review


def test_rules_two_classes():
    assert rule_based_filter("quais painéis precisam limpar?", NOW).labels == [Label.SEVERO]
    assert rule_based_filter("quais não precisam de limpeza", NOW).labels == [Label.LIMPO]
    assert rule_based_filter("fotos limpas e sujas", NOW).labels == [Label.LIMPO, Label.SEVERO]
    assert rule_based_filter("painéis empoeirados", NOW).labels == [Label.SEVERO]


def test_deterministic_summary_uses_two_classes():
    text, src = Assistant(None).summarize("q", SearchFilter(labels=[Label.SEVERO]), 2, STATS)
    assert src == "regras" and "8 não precisam de limpeza e 2 precisam de limpeza" in text and "precisa limpar" in text
    one = Assistant(None).summarize("q", SearchFilter(), 2, {**STATS, "total": 2, "por_rotulo": {"LIMPO": 1, "SEVERO": 1}})[0]
    assert "1 não precisa de limpeza e 1 precisa de limpeza" in one


def test_interpret_gemini_and_fallback():
    a = Assistant(Fake({"labels": ["SEVERO"], "needs_review": True}))
    f, src = a.interpret("x", NOW)
    assert src == "gemini" and f.labels == [Label.SEVERO]
    f, src = Assistant(Fake({"labels": ["NADA"]})).interpret("fotos limpas", NOW)       # inválido -> regras
    assert src == "regras" and f.labels == [Label.LIMPO]
    assert Assistant(Fake(boom=True)).interpret("fotos limpas", NOW)[1] == "regras"
    assert Assistant(None).interpret("fotos limpas", NOW)[1] == "regras"


def test_summary_rejects_invented_numbers():
    f = SearchFilter()
    ok, src = Assistant(Fake(text="Há 10 fotos, 2 severas.")).summarize("q", f, 10, STATS)
    assert src == "gemini"
    bad, src = Assistant(Fake(text="Há 10 fotos, 87% severas.")).summarize("q", f, 10, STATS)
    assert src == "regras" and "87" not in bad
    assert Assistant(Fake(boom=True)).summarize("q", f, 10, STATS)[1] == "regras"


def test_gemini_client_http():
    def handler(req: httpx.Request):
        assert req.headers["x-goog-api-key"] == "k" and "m1:generateContent" in str(req.url)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "```json\n{\"labels\":[\"LIMPO\"]}\n```"}]}}]})
    c = GeminiClient("k", "m1", transport=httpx.MockTransport(handler))
    assert c.generate_json("p") == {"labels": ["LIMPO"]}
    bad = GeminiClient("k", "m1", transport=httpx.MockTransport(lambda r: httpx.Response(429, text="cota")))
    try:
        bad.generate("p"); assert False
    except GeminiError as e:
        assert "429" in str(e)
