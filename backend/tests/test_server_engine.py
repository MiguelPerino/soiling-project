"""Modo "servidor" (modelo grande ONNX, binário) ao lado do modo ESP32: dois modos, sem comparação.

O modelo de teste tem o MESMO formato do ResNet50 do time (tests/server_tiny_model.py): NHWC 0..255, saída probs,
labels NaoLimpar/Limpar, classe_positiva Limpar e limiar 0,19.
"""
import io
import json
import zipfile

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.api.routes import create_app
from app.config import Settings
from app.labels import Label, UnknownClassError, parse_classes
from app.services.assistant.service import Assistant
from app.services.esp32 import Esp32Client
from app.services.server_model import ServerModel, ServerModelUnavailable, map_classes, try_load
from app.services.storage import ImageStore
from tests.conftest import BLUE, DOUBT, KEY, RED, make_jpeg, post
from tests.server_tiny_model import VERSION, build_server_model, p_limpar


def test_server_engine_classifies_and_never_pumps(client):
    r = post(client, make_jpeg(BLUE, size=(200, 120)), headers=KEY, engine="server", pump="true")
    j = r.json()
    a = j["analise"]
    assert r.status_code == 200 and a["engine"] == "server" and a["classification"] == "SEVERO"
    assert a["cleaning_activated"] is False and a["pump_duration_ms"] == 0 and "não aciona a bomba" in a["pump_reason"]
    assert j["bomba_bloqueada_por_falta_de_chave"] is False                     # não há bomba para bloquear
    assert set(a["probs"]) == {"LIMPO", "SEVERO"} and a["model_version"] == VERSION
    assert a["probs"]["LIMPO"] + a["probs"]["SEVERO"] == pytest.approx(1.0)
    assert a["low_confidence"] is False and a["acao_sugerida"] == "acionar_limpeza"
    assert (a["width"], a["height"]) == (200, 120)
    assert client.app.state.esp32.status()["online"]                            # o simulador seguiu intocado
    assert client.get("/api/stats").json()["limpezas_acionadas"] == 0


def test_server_clean_photo(client):
    a = post(client, make_jpeg(RED), engine="server").json()["analise"]
    assert a["classification"] == "LIMPO" and a["confidence"] > 0.9 and a["acao_sugerida"] == "nenhuma"
    assert a["confidence"] == pytest.approx(a["probs"]["LIMPO"])                # confiança = P(classe escolhida)


def test_threshold_and_doubt_band(client):
    """Limiar 0,19 (não argmax): P(Limpar) ~0,30 já é 'precisa limpar', mas cai na faixa de dúvida (< 0,50) => revisar."""
    a = post(client, make_jpeg(DOUBT), engine="server").json()["analise"]
    assert 0.19 <= a["probs"]["SEVERO"] < 0.5
    assert a["classification"] == "SEVERO" and a["confidence"] == pytest.approx(a["probs"]["SEVERO"])
    assert a["low_confidence"] and a["needs_review"] and a["acao_sugerida"] == "revisar"
    assert client.get("/api/stats").json()["para_revisao"] == 1


def test_decide_rule(server_model):
    assert (server_model.threshold, server_model.review_until) == (0.19, 0.5)
    assert server_model.decide(0.18) == (Label.LIMPO, pytest.approx(0.82), False)
    assert server_model.decide(0.19)[0] == Label.SEVERO and server_model.decide(0.19)[2]       # no limiar: precisa limpar, revisar
    assert server_model.decide(0.49)[2] and not server_model.decide(0.5)[2]
    assert server_model.decide(0.95) == (Label.SEVERO, 0.95, False)


def test_preprocess_matches_the_model_contract(server_model):
    from PIL import Image
    x = server_model.preprocess(Image.new("RGB", (80, 40), (200, 100, 50)))
    assert x.shape == (1, 32, 32, 3) and x.dtype == np.float32                   # NHWC, enquadrada (imagem lisa: só recorta)
    assert x[0, 0, 0].tolist() == [200.0, 100.0, 50.0]                           # 0..255, sem normalizar (vive no ONNX)
    p = server_model.predict(Image.new("RGB", (32, 32), DOUBT))
    assert p.p_positive == pytest.approx(p_limpar(DOUBT), abs=1e-5)              # saída já é probabilidade: sem 2º softmax


def test_config_exposes_threshold_and_review_band(client):
    srv = client.get("/api/config").json()["engines"]["server"]
    assert srv["classes"] == ["LIMPO", "SEVERO"] and srv["limiar"] == 0.19 and srv["revisao_ate"] == 0.5
    assert srv["versao"] == VERSION and srv["input_size"] == 32 and srv["aciona_bomba"] is False
    assert srv["enquadramento"] == "panel"


def test_review_until_from_settings_and_card(tmp_path):
    d = build_server_model(tmp_path / "a")
    assert ServerModel.load(d, review_until=0.7).review_until == 0.7
    assert ServerModel.load(d, review_until=0.1).review_until == 0.19              # nunca abaixo do limiar
    d2 = build_server_model(tmp_path / "b", extra_card={"decisao": {"limiar": 0.3, "revisao_ate": 0.6}})
    m = ServerModel.load(d2, review_until=0.9)
    assert (m.threshold, m.review_until) == (0.3, 0.6)                             # o card manda


def test_class_mapping():
    assert map_classes(["NaoLimpar", "Limpar"], {"classe_positiva": "Limpar"}) == (Label.LIMPO, Label.SEVERO)
    assert map_classes(["Limpar", "NaoLimpar"], {"classe_positiva": "limpar"}) == (Label.SEVERO, Label.LIMPO)
    assert map_classes(["LIMPO", "SEVERO"], {}) == (Label.LIMPO, Label.SEVERO)       # nomes do sistema dispensam o card
    for names, card in ((["A", "B"], {}), (["A", "B"], {"classe_positiva": "C"}), (["A", "A"], {"classe_positiva": "A"}),
                        (["A", "B", "C"], {"classe_positiva": "A"}), ("AB", {})):
        with pytest.raises(ValueError):
            map_classes(names, card)


def test_reversed_output_order(tmp_path):
    """Se o labels.json disser que a saída 0 é Limpar, é ela que vira SEVERO."""
    d = build_server_model(tmp_path / "rev", labels=("Limpar", "NaoLimpar"))      # saída 0 (canal R) agora é Limpar
    from PIL import Image
    assert ServerModel.load(d).predict(Image.new("RGB", (32, 32), RED)).label == Label.SEVERO


def test_nchw_logits_model_still_works(tiny_dir):
    """Modelo NCHW com logits e nomes do sistema (o sintético do simulador): layout lido do ONNX, softmax aplicado."""
    from PIL import Image
    m = ServerModel.load(tiny_dir)
    assert not m.nhwc and not m.outputs_probs and not m.raw_0_255 and m.threshold == 0.5
    assert m.predict(Image.new("RGB", (32, 32), BLUE)).label == Label.SEVERO
    assert m.predict(Image.new("RGB", (32, 32), RED)).label == Label.LIMPO


def test_server_engine_does_not_call_the_esp32(repo, settings, server_model):
    def boom(request):
        raise AssertionError("o ESP32 não deveria ser chamado no modo servidor")
    esp = Esp32Client("http://esp.local", "k", transport=httpx.MockTransport(boom))
    app = create_app(settings, repo=repo, esp32=esp, assistant=Assistant(None), store=ImageStore(settings.storage_dir),
                     server_model=server_model)
    with TestClient(app) as c:
        assert post(c, make_jpeg(RED), engine="server").status_code == 200


def test_default_engine_is_esp32_and_only_two_modes(client):
    assert post(client, make_jpeg(RED), headers=KEY).json()["analise"]["engine"] == "esp32"
    assert post(client, make_jpeg(RED, noise_seed=2), headers=KEY, engine="both").status_code == 422     # comparar não existe


def test_server_model_missing_is_503_and_stores_nothing(repo, settings, simulator, tmp_path):
    _, url = simulator
    app = create_app(settings, repo=repo, esp32=Esp32Client(url, "chave-esp"), assistant=Assistant(None),
                     store=ImageStore(settings.storage_dir))                      # sem server_model: SERVER_MODEL_DIR não existe
    with TestClient(app) as c:
        cfg = c.get("/api/config").json()["engines"]
        assert cfg["server"]["disponivel"] is False and "faltam" in cfg["server"]["motivo"] and cfg["server"]["limiar"] is None
        assert c.get("/api/health").json()["modelo_servidor"] is False
        r = post(c, make_jpeg(RED), engine="server")
        assert r.status_code == 503 and "indisponível" in r.json()["detail"]
        assert c.get("/api/stats").json()["total"] == 0 and not any(c.app.state.store.root.rglob("*.jpg"))
        assert post(c, make_jpeg(RED), headers=KEY, pump="false").status_code == 200     # o modo ESP32 segue funcionando


def test_stats_and_filter_by_engine(client):
    post(client, make_jpeg(RED), headers=KEY, pump="false")
    post(client, make_jpeg(BLUE, noise_seed=1), engine="server")
    post(client, make_jpeg(RED, noise_seed=2), engine="server")
    st = client.get("/api/stats").json()
    assert st["por_motor"] == {"esp32": 1, "server": 2} and st["por_rotulo"] == {"LIMPO": 2, "SEVERO": 1}
    assert set(st["serie_diaria"][-1]) == {"dia", "LIMPO", "SEVERO"}
    assert client.get("/api/analyses", params={"engine": "server"}).json()["total"] == 2
    assert client.get("/api/analyses", params={"engine": "esp32"}).json()["itens"][0]["engine"] == "esp32"
    assert client.get("/api/analyses", params={"engine": "both"}).status_code == 422
    assert client.get("/api/analyses", params={"labels": "MODERADO"}).status_code == 422          # classe que não existe mais


def test_relabel_only_two_classes(client):
    a = post(client, make_jpeg(RED), engine="server").json()["analise"]
    assert client.patch(f"/api/analyses/{a['id']}/label", json={"label": "MODERADO"}, headers=KEY).status_code == 422
    b = client.patch(f"/api/analyses/{a['id']}/label", json={"label": "SEVERO"}, headers=KEY).json()
    assert b["final_label"] == "SEVERO" and b["classification"] == "LIMPO"


def test_export_training_zip(client):
    ids = [post(client, make_jpeg(c, noise_seed=i), headers=KEY, engine=e, pump="false").json()["analise"]["id"]
           for i, (c, e) in enumerate([(RED, "esp32"), (BLUE, "server"), (RED, "server")])]
    assert client.get("/api/export/training.zip").status_code == 401                # exige chave de administrador
    assert client.get("/api/export/training.zip", headers=KEY).status_code == 404   # ninguém revisou ainda
    client.patch(f"/api/analyses/{ids[0]}/label", json={"label": "SEVERO"}, headers=KEY)
    client.patch(f"/api/analyses/{ids[1]}/label", json={"label": "SEVERO"}, headers=KEY)
    r = client.get("/api/export/training.zip", headers=KEY)
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert r.headers["content-type"] == "application/zip"
    assert sorted(z.namelist()) == sorted([f"SEVERO/{ids[0]}.jpg", f"SEVERO/{ids[1]}.jpg", "labels.csv"])
    assert z.read(f"SEVERO/{ids[1]}.jpg")[:2] == b"\xff\xd8" and "server" in z.read("labels.csv").decode()
    everything = zipfile.ZipFile(io.BytesIO(client.get("/api/export/training.zip", params={"only_reviewed": "false"}, headers=KEY).content))
    assert len(everything.namelist()) == 4 and f"LIMPO/{ids[2]}.jpg" in everything.namelist()
    only_server = zipfile.ZipFile(io.BytesIO(client.get("/api/export/training.zip", params={"engine": "server"}, headers=KEY).content))
    assert sorted(only_server.namelist()) == sorted([f"SEVERO/{ids[1]}.jpg", "labels.csv"])


# ---------- classes e tamanhos são configuráveis ----------
def test_parse_classes():
    assert [l.value for l in parse_classes("LIMPO, SEVERO")] == ["LIMPO", "SEVERO"]
    assert [l.value for l in parse_classes(["severo", "limpo"])] == ["SEVERO", "LIMPO"]
    for bad in ("LIMPO,MODERADO,SEVERO", "LIMPO,MODERADO", "LIMPO,LIMPO,SEVERO", "LIMPO,SEVERO,XYZ", "SEVERO", ""):
        with pytest.raises(UnknownClassError):
            parse_classes(bad)


def test_settings_from_env(monkeypatch):
    for k in ("ESP32_CLASSES", "ESP32_INPUT_SIZE", "SERVER_INPUT_SIZE", "SERVER_REVIEW_UNTIL", "SERVER_FRAMING", "INPUT_SIZE"):
        monkeypatch.delenv(k, raising=False)
    d = Settings.from_env()                                                           # padrão = modelo do ESP32 (soilnet 2x: binário, 112)
    assert d.esp32_classes == ("LIMPO", "SEVERO") and d.input_size == 112 and d.server_input_size == 0
    assert d.server_review_until == 0.5 and d.server_framing == "panel"
    monkeypatch.setenv("ESP32_INPUT_SIZE", "128")
    monkeypatch.setenv("SERVER_INPUT_SIZE", "256")
    monkeypatch.setenv("SERVER_REVIEW_UNTIL", "0.6")
    monkeypatch.setenv("SERVER_FRAMING", "None")
    s = Settings.from_env()
    assert s.input_size == 128 and s.server_input_size == 256 and s.server_review_until == 0.6 and s.server_framing == "none"
    monkeypatch.delenv("ESP32_INPUT_SIZE")
    monkeypatch.setenv("INPUT_SIZE", "64")                                          # nome antigo continua valendo
    assert Settings.from_env().input_size == 64
    monkeypatch.setenv("ESP32_CLASSES", "LIMPO,MODERADO,SEVERO")
    with pytest.raises(UnknownClassError):
        Settings.from_env()


def test_esp32_answer_outside_the_two_classes_is_rejected(repo, settings):
    def handler(request):
        return httpx.Response(200, json={"classification": "MODERADO", "confidence": 0.9})
    esp = Esp32Client("http://esp.local", "k", transport=httpx.MockTransport(handler), classes=("LIMPO", "SEVERO"))
    app = create_app(settings, repo=repo, esp32=esp, assistant=Assistant(None), store=ImageStore(settings.storage_dir))
    with TestClient(app) as c:
        assert post(c, make_jpeg(RED), headers=KEY, pump="false").status_code == 502
        assert c.get("/api/stats").json()["total"] == 0


def test_server_input_size_is_adjustable(server_dir):
    assert ServerModel.load(server_dir).size == 32                                  # padrão: model_card.json


def test_server_model_loader_errors(server_dir, tmp_path):
    model, why = try_load(str(tmp_path / "nao-existe"))
    assert model is None and "faltam" in why
    three = build_server_model(tmp_path / "tres", labels=("NaoLimpar", "Limpar"), outputs=3)
    model, why = try_load(str(three))
    assert model is None and "3 saídas" in why                                     # o sistema é binário
    bad = tmp_path / "bad"
    bad.mkdir()
    for n in ("model.onnx", "model_card.json"):
        (bad / n).write_bytes(open(f"{server_dir}/{n}", "rb").read())
    (bad / "labels.json").write_text(json.dumps(["NaoLimpar", "Limpar", "Talvez"]))
    assert "inválido" in try_load(str(bad))[1]
    (bad / "labels.json").write_text(json.dumps(["Sujo", "Ok"]))                     # classe_positiva do card não está aqui
    assert "classe_positiva" in try_load(str(bad))[1]
    no_pos = build_server_model(tmp_path / "sem-positiva", positive=None)
    assert "classe_positiva" in try_load(str(no_pos))[1]
    bad_thr = build_server_model(tmp_path / "limiar", extra_card={"decisao": {"limiar": 1.5}})
    assert "limiar" in try_load(str(bad_thr))[1]
    with pytest.raises(ServerModelUnavailable):
        ServerModel.load(tmp_path / "vazia")


def test_old_database_gets_the_engine_column(tmp_path):
    from sqlalchemy import create_engine, text
    from app.database.repository import Repository
    url = f"sqlite:///{tmp_path}/velho.db"
    old = create_engine(url)
    with old.begin() as c:                                                           # tabela como era antes do modo servidor
        c.execute(text("CREATE TABLE analyses (id INTEGER PRIMARY KEY AUTOINCREMENT, image_path VARCHAR(300) NOT NULL, "
                       "original_filename VARCHAR(255), classification VARCHAR(10) NOT NULL, confidence FLOAT NOT NULL, probs JSON, "
                       "low_confidence BOOLEAN, cleaning_activated BOOLEAN, pump_duration_ms INTEGER, pump_reason VARCHAR(200), "
                       "dirt_level FLOAT, model_version VARCHAR(80), inference_ms INTEGER, round_trip_ms INTEGER, width INTEGER NOT NULL, "
                       "height INTEGER NOT NULL, human_label VARCHAR(10), reviewed_at DATETIME, created_at DATETIME)"))
        c.execute(text("INSERT INTO analyses (image_path, classification, confidence, width, height) VALUES ('a.jpg','LIMPO',0.9,96,96)"))
    old.dispose()
    r = Repository(url)
    r.create_schema()
    assert r.get(1)["engine"] == "esp32"                                              # linhas antigas contam como ESP32
    r.dispose()


def test_old_row_with_removed_class_does_not_break_the_api(client):
    a = post(client, make_jpeg(RED), engine="server").json()["analise"]
    from sqlalchemy import text
    with client.app.state.repo.session() as s:                                     # simula uma análise antiga de 3 classes
        s.execute(text("UPDATE analyses SET classification = 'MODERADO' WHERE id = :i"), {"i": a["id"]})
        s.commit()
    j = client.get("/api/analyses").json()
    assert j["total"] == 1 and j["itens"][0]["acao_sugerida"] == "revisar"
    assert client.get("/api/stats").json()["por_rotulo"] == {"LIMPO": 0, "SEVERO": 0}
