"""Treina o classificador BINÁRIO do ESP32 (Keras), escolhe o limiar na validação, exporta TFLite int8 e avalia no teste.

    python training/train.py --manifest data/manifest.csv --size 112 --epochs 40 --out models/run1
    cp -r models/run1 models/current        # a pasta "current" é o que o simulador usa (scripts/dev.sh)

Classes: LIMPO = NAOLIMPAR (índice 0, "Não precisa limpar") e SEVERO = LIMPAR (índice 1, "Precisa limpar", a positiva).
A saída segue o MESMO formato do soilnet v1, que o firmware e o simulador já usam:
  labels.json      ["NAOLIMPAR", "LIMPAR"]
  model_card.json  input_size, positive_label, limiar_limpar, low_confidence_threshold, rgb565, jpeg_quality, resize_mode...
  model.tflite     entrada (1, size, size, 3) int8, saída (1, 2) int8 (softmax)
No fim, o script imprime os valores [MODELO] para copiar em firmware/esp32/src/config.h.

Decisões (todas ligadas ao ESP32 esp32dev, SEM PSRAM, ~320 KB de RAM utilizável):
- rede pequena (depthwise-separable, ~25 mil parâmetros): cabe em ~100 KB de modelo int8;
- normalização DENTRO do modelo (Rescaling): o firmware só entrega pixels RGB 0-255 e quantiza com a escala do tensor;
- as imagens de treino passam pelo MESMO caminho da implantação: esticadas para size×size, JPEG na qualidade do backend e
  truncadas para RGB565 (o firmware decodifica o JPEG em RGB565);
- decisão por LIMIAR na classe positiva (não argmax), escolhido na validação int8 pelo maior F1 macro;
- a BOMBA exige confiança >= max(limiar, PUMP_FLOOR=0,5): um limiar baixo (ex.: 0,19) classifica "Precisa limpar" cedo, mas
  só aciona água com o modelo seguro; entre os dois, o resultado vai para revisão humana;
- seleção do melhor epoch por F1 macro na validação; o teste só é lido no fim.
Nenhum número de acurácia é prometido aqui: ele sai de metrics.json depois do treino com os SEUS dados.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

from labels import LABELS, MODEL_NAMES, POSITIVE
from metrics import auc, choose_threshold, predict, selective, summarize

SEED = 42
PUMP_FLOOR = 0.5     # a bomba nunca aciona com P(LIMPAR) abaixo disto, mesmo que o limiar de decisão escolhido seja menor


# ---------------------------------------------------------------- dados
def to_rgb565(rgb: np.ndarray) -> np.ndarray:
    """Trunca para RGB565 e expande de volta a 8 bits como o firmware (main.cpp: fillInput) e o simulador (to_rgb565)."""
    q = np.asarray(rgb).astype(np.int32)
    r, g, b = q[..., 0] >> 3, q[..., 1] >> 2, q[..., 2] >> 3
    return np.stack([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)], axis=-1).astype(np.uint8)


def deploy_view(img: Image.Image, size: int, jpeg_quality: int, rgb565: bool) -> np.ndarray:
    """O que o ESP32 vê: esticada para size×size (backend: esp32_jpeg), JPEG, decodificada (em RGB565 no firmware)."""
    buf = BytesIO()
    img.convert("RGB").resize((size, size), Image.BILINEAR).save(buf, "JPEG", quality=jpeg_quality)
    arr = np.asarray(Image.open(BytesIO(buf.getvalue())).convert("RGB"), dtype=np.uint8)
    return to_rgb565(arr) if rgb565 else arr


def load_split(manifest: Path, split: str, size: int, jpeg_quality: int, rgb565: bool) -> tuple[np.ndarray, np.ndarray]:
    xs, ys = [], []
    with manifest.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["split"] != split:
                continue
            if r["label"] not in LABELS:
                raise SystemExit(f"rótulo {r['label']!r} em {manifest}: o modelo é binário ({LABELS}). Rode prepare_data.py de novo.")
            with Image.open(r["path"]) as img:
                xs.append(deploy_view(img, size, jpeg_quality, rgb565))
            ys.append(LABELS.index(r["label"]))
    if not xs:
        raise SystemExit(f"partição '{split}' vazia em {manifest}. Rode prepare_data.py (use --resplit se preciso).")
    return np.stack(xs), np.asarray(ys, dtype=np.int64)


# ---------------------------------------------------------------- modelo
def build_model(size: int, arch: str = "tiny_cnn"):
    import keras
    from keras import layers

    inp = keras.Input((size, size, 3), name="input")                 # RGB 0..255
    x = layers.Rescaling(1 / 127.5, offset=-1.0)(inp)                 # -> [-1, 1]
    if arch == "tiny_cnn":
        x = layers.Conv2D(8, 3, strides=2, padding="same", use_bias=False)(x)
        x = layers.BatchNormalization(momentum=0.9)(x); x = layers.ReLU(6.0)(x)
        for filters, stride in [(16, 2), (24, 2), (32, 2), (48, 1), (64, 2)]:
            x = layers.DepthwiseConv2D(3, strides=stride, padding="same", use_bias=False)(x)
            x = layers.BatchNormalization(momentum=0.9)(x); x = layers.ReLU(6.0)(x)
            x = layers.Conv2D(filters, 1, use_bias=False)(x)
            x = layers.BatchNormalization(momentum=0.9)(x); x = layers.ReLU(6.0)(x)
        x = layers.GlobalAveragePooling2D()(x)
    else:
        raise SystemExit(f"arquitetura desconhecida: {arch}. Disponível: tiny_cnn")
    x = layers.Dropout(0.2)(x)
    out = layers.Dense(len(LABELS), activation="softmax", name="probs")(x)   # 2 saídas: [P(NAOLIMPAR), P(LIMPAR)]
    return keras.Model(inp, out, name=arch)


def augmenter():
    import keras
    from keras import layers
    return keras.Sequential([
        layers.RandomFlip("horizontal_and_vertical"),
        layers.RandomRotation(0.04, fill_mode="reflect"),
        layers.RandomTranslation(0.05, 0.05, fill_mode="reflect"),
        layers.RandomBrightness(0.2, value_range=(0, 255)),
        layers.RandomContrast(0.2),
    ], name="aug")


def class_weights(y: np.ndarray) -> dict[int, float]:
    n = np.bincount(y, minlength=len(LABELS)).astype(float)
    n[n == 0] = 1
    return {i: float(len(y) / (len(LABELS) * n[i])) for i in range(len(LABELS))}


class BestF1:
    """Guarda os melhores pesos pela validação: maior F1 macro no corte 0,5 e, no empate, menor perda (log-loss).
    O desempate importa: com dados fáceis o F1 chega a 1,0 cedo, e sem ele ficaria o primeiro epoch (pouco confiante).
    O limiar de operação é escolhido DEPOIS, com o modelo final (choose_threshold)."""
    def __init__(self, model, xv, yv, patience: int):
        import keras
        self.cb = keras.callbacks.LambdaCallback(on_epoch_end=self.on_epoch_end)
        self.model, self.xv, self.yv, self.patience = model, xv, yv, patience
        self.best, self.best_w, self.wait, self.history = None, None, 0, []

    def on_epoch_end(self, epoch, logs=None):
        probs = self.model.predict(self.xv.astype("float32"), verbose=0)
        f1 = summarize(self.yv, predict(probs[:, POSITIVE], 0.5))["f1_macro"]
        loss = float(-np.mean(np.log(np.clip(probs[np.arange(len(self.yv)), self.yv], 1e-7, 1.0))))
        self.history.append({"epoca": epoch + 1, "val_f1_macro_corte_0_5": f1, "val_loss": loss, "loss": float(logs["loss"])})
        print(f"  época {epoch + 1}: val F1 macro (corte 0,5) = {f1:.3f}  val loss = {loss:.3f}")
        score = (round(f1, 4), -loss)
        if self.best is None or score > self.best:
            self.best, self.best_w, self.wait = score, self.model.get_weights(), 0
        else:
            self.wait += 1
            if self.wait >= self.patience:
                self.model.stop_training = True


# ---------------------------------------------------------------- exportação
def to_tflite_int8(model, x_rep: np.ndarray) -> bytes:
    import tensorflow as tf
    conv = tf.lite.TFLiteConverter.from_keras_model(model)
    conv.optimizations = [tf.lite.Optimize.DEFAULT]
    rep = x_rep[np.random.default_rng(SEED).permutation(len(x_rep))[:200]].astype("float32")
    conv.representative_dataset = lambda: ([r[None]] for r in rep)
    conv.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    conv.inference_input_type = tf.int8
    conv.inference_output_type = tf.int8
    return conv.convert()


def _interpreter(blob: bytes):
    try:
        from ai_edge_litert.interpreter import Interpreter
    except ImportError:
        from tensorflow.lite import Interpreter
    it = Interpreter(model_content=blob)
    it.allocate_tensors()
    return it


def tflite_info(blob: bytes) -> dict:
    it = _interpreter(blob)
    i, o = it.get_input_details()[0], it.get_output_details()[0]
    try:
        ops = sorted({d["op_name"] for d in it._get_ops_details()} - {"DELEGATE"})      # API interna; só informativa
    except Exception:
        ops = []
    return {"input": {"shape": [int(v) for v in i["shape"]], "dtype": "int8", "scale": float(i["quantization"][0]), "zero_point": int(i["quantization"][1])},
            "output": {"shape": [int(v) for v in o["shape"]], "dtype": "int8", "scale": float(o["quantization"][0]), "zero_point": int(o["quantization"][1])},
            "ops": ops}


def tflite_predict(blob: bytes, x: np.ndarray) -> np.ndarray:
    """Roda o TFLite int8 exatamente como o firmware: quantiza a entrada, lê a saída e desquantiza."""
    it = _interpreter(blob)
    i, o = it.get_input_details()[0], it.get_output_details()[0]
    si, zi = i["quantization"]
    so, zo = o["quantization"]
    out = []
    for img in x:
        q = np.clip(np.round(img.astype("float32") / si + zi), -128, 127).astype(np.int8)[None]
        it.set_tensor(i["index"], q)
        it.invoke()
        out.append((it.get_tensor(o["index"])[0].astype("float32") - zo) * so)
    return np.asarray(out)


def evaluate(probs: np.ndarray, y: np.ndarray, threshold: float, pump: float) -> dict:
    p_pos = probs[:, POSITIVE]
    m = summarize(y, predict(p_pos, threshold))
    m["limiar"] = threshold
    m["auc_roc"] = auc(y, p_pos)
    m["no_corte_0_5"] = summarize(y, predict(p_pos, 0.5))
    m["bomba"] = selective(p_pos, y, threshold, pump)
    return m


def build_card(*, version: str, arch: str, size: int, jpeg_quality: int, rgb565: bool, threshold: float, pump: float,
               params: int, blob_len: int, info: dict, counts: dict, weights: dict, val_f1_float: float,
               val_f1_int8: float, test: dict) -> dict:
    """model_card.json no formato do soilnet v1 (lido pelo simulador: tflite_engine.py; espelhado no config.h do firmware)."""
    return {
        "version": version, "task": "binario", "arch": arch, "input_size": size,
        "labels": list(MODEL_NAMES), "positive_label": MODEL_NAMES[POSITIVE],
        "resize_mode": "stretch", "jpeg_quality": jpeg_quality, "rgb565": rgb565,
        "limiar_nao_limpar": threshold, "limiar_limpar": threshold, "low_confidence_threshold": pump,
        "parameters": params, "tflite_bytes": blob_len, "tflite": info, "trained_on": counts,
        "class_weight": {MODEL_NAMES[i]: w for i, w in weights.items()},
        "val_f1_macro_float": val_f1_float, "val_f1_macro_int8": val_f1_int8,
        "test_accuracy_int8": test["acuracia"], "test_f1_macro_int8": test["f1_macro"], "test_auc_int8": test["auc_roc"],
        "nota": "A RAM real (tensor arena) só se mede no ESP32. Veja docs/04_FIRMWARE_ESP32.md.",
    }


def config_h_snippet(card: dict) -> str:
    """Os itens [MODELO] de firmware/esp32/src/config.h para este modelo (o firmware não lê o model_card sozinho)."""
    return (f"constexpr int      INPUT_SIZE          = {card['input_size']};\n"
            f"constexpr int      NUM_CLASSES         = {len(card['labels'])};\n"
            f'static const char *const CLASS_NAMES[NUM_CLASSES] = {{"{LABELS[0]}", "{LABELS[1]}"}};\n'
            f"constexpr int      POSITIVE_CLASS      = {card['labels'].index(card['positive_label'])};\n"
            f"constexpr float    DECISION_THRESHOLD  = {card['limiar_limpar']:.2f}f;\n"
            f"constexpr float    CONF_THRESHOLD      = {card['low_confidence_threshold']:.2f}f;\n"
            f'#define MODEL_VERSION "{card["version"]}"')


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", type=Path, default=Path("data/manifest.csv"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--size", type=int, default=112, help="igual a ESP32_INPUT_SIZE do backend e INPUT_SIZE do firmware")
    ap.add_argument("--arch", default="tiny_cnn")
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--patience", type=int, default=8)
    ap.add_argument("--jpeg-quality", type=int, default=85, help="igual a JPEG_QUALITY do backend")
    ap.add_argument("--no-rgb565", action="store_true", help="não simular a decodificação RGB565 do firmware (não recomendado)")
    ap.add_argument("--threshold", type=float, default=None,
                    help="limiar de decisão P(LIMPAR); padrão: escolhido na validação int8 pelo maior F1 macro")
    ap.add_argument("--pump-threshold", type=float, default=None,
                    help=f"confiança mínima para a bomba (CONF_THRESHOLD do firmware); padrão: max(limiar, {PUMP_FLOOR})")
    a = ap.parse_args()
    rgb565 = not a.no_rgb565

    import keras
    import tensorflow as tf
    keras.utils.set_random_seed(SEED)

    xt, yt = load_split(a.manifest, "train", a.size, a.jpeg_quality, rgb565)
    xv, yv = load_split(a.manifest, "val", a.size, a.jpeg_quality, rgb565)
    xs, ys = load_split(a.manifest, "test", a.size, a.jpeg_quality, rgb565)
    print(f"treino {len(xt)} | validação {len(xv)} | teste {len(xs)}  classes treino {dict(zip(LABELS, np.bincount(yt, minlength=2).tolist()))}")

    model = build_model(a.size, a.arch)
    print(f"parâmetros: {model.count_params():,}")
    aug = augmenter()
    ds = (tf.data.Dataset.from_tensor_slices((xt.astype("float32"), yt)).shuffle(len(xt), seed=SEED)
          .batch(a.batch).map(lambda x, y: (aug(x, training=True), y), num_parallel_calls=tf.data.AUTOTUNE).prefetch(2))
    steps = max(1, a.epochs * int(np.ceil(len(xt) / a.batch)))
    lr = keras.optimizers.schedules.CosineDecay(a.lr, steps)
    model.compile(keras.optimizers.Adam(lr), "sparse_categorical_crossentropy", metrics=["accuracy"])
    best = BestF1(model, xv, yv, a.patience)
    weights = class_weights(yt)
    model.fit(ds, epochs=a.epochs, class_weight=weights, callbacks=[best.cb], verbose=0)
    model.set_weights(best.best_w)

    a.out.mkdir(parents=True, exist_ok=True)
    model.save(a.out / "model.keras")
    blob = to_tflite_int8(model, xt)
    (a.out / "model.tflite").write_bytes(blob)
    info = tflite_info(blob)

    # limiar escolhido na VALIDAÇÃO com o modelo int8 (é ele que roda no ESP32); o teste só é usado para relatar
    val_float = choose_threshold(yv, model.predict(xv.astype("float32"), verbose=0)[:, POSITIVE])
    val_int8 = choose_threshold(yv, tflite_predict(blob, xv)[:, POSITIVE])
    threshold = round(a.threshold if a.threshold is not None else val_int8["limiar"], 2)
    pump = round(a.pump_threshold if a.pump_threshold is not None else max(threshold, PUMP_FLOOR), 2)
    if pump < PUMP_FLOOR:
        print(f"AVISO: --pump-threshold {pump} < {PUMP_FLOOR}: a bomba poderá acionar com o modelo pouco seguro.")

    keras_metrics = evaluate(model.predict(xs.astype("float32"), verbose=0), ys, threshold, pump)
    tfl_metrics = evaluate(tflite_predict(blob, xs), ys, threshold, pump)
    version = f"{a.arch}-{a.size}-{dt.date.today():%Y%m%d}"
    card = build_card(version=version, arch=a.arch, size=a.size, jpeg_quality=a.jpeg_quality, rgb565=rgb565,
                      threshold=threshold, pump=pump, params=int(model.count_params()), blob_len=len(blob), info=info,
                      counts={"train": len(xt), "val": len(xv), "test": len(xs)}, weights=weights,
                      val_f1_float=val_float["f1_macro_validacao"], val_f1_int8=val_int8["f1_macro_validacao"], test=tfl_metrics)
    (a.out / "labels.json").write_text(json.dumps(list(MODEL_NAMES)), encoding="utf-8")
    (a.out / "model_card.json").write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
    (a.out / "metrics.json").write_text(json.dumps({"limiar_escolhido_na_validacao": {"float": val_float, "int8": val_int8},
                                                    "teste_keras_float": keras_metrics, "teste_tflite_int8": tfl_metrics,
                                                    "validacao_f1_por_epoca": best.history}, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nlimiar P(LIMPAR) = {threshold:.2f} (validação int8, F1 macro {val_int8['f1_macro_validacao']:.3f}); bomba exige >= {pump:.2f}")
    print(f"TESTE  float: acc {keras_metrics['acuracia']:.3f}  F1 macro {keras_metrics['f1_macro']:.3f}")
    print(f"TESTE  int8 : acc {tfl_metrics['acuracia']:.3f}  F1 macro {tfl_metrics['f1_macro']:.3f}  AUC {tfl_metrics['auc_roc'] or 0:.3f}   (é este que roda no ESP32)")
    print(f"  limpos que acionariam: {tfl_metrics['limpos_que_acionariam_pct']:.1%} | sujos ignorados: {tfl_metrics['sujos_ignorados_pct']:.1%}")
    print("matriz de confusão (linhas=real, colunas=previsto; ordem", list(LABELS), "):")
    for row in tfl_metrics["matriz_confusao"]:
        print("  ", row)
    print(f"modelo TFLite: {len(blob) / 1024:.1f} KB | ops: {', '.join(info['ops']) or 'n/d'}")
    print(f"salvo em {a.out}\n\nPara o firmware, copie em firmware/esp32/src/config.h (itens [MODELO]):\n{config_h_snippet(card)}")
    print(f"e no backend: ESP32_INPUT_SIZE={a.size} ESP32_CLASSES=LIMPO,SEVERO")


if __name__ == "__main__":
    main()
