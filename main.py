import json, os, re, secrets, threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

PORT = 8000
TZ = timezone(timedelta(hours=2))  # Moçambique
AQUI = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(os.environ.get("ANDROID_PRIVATE") or AQUI, "megaflow.json")
LOCK = threading.Lock()
RE_PAG = re.compile(r"Confirmado\s+([A-Z0-9]+)\.\s+Recebeste\s+([\d.,]+)MT\s+de\s+(258\d{9})", re.I)
RE_ENV = re.compile(r"Transferiste\s+(\d+)\s*MB.*?numero\s+(?:258)?(\d{9})", re.I | re.S)
J, T = "application/json", "text/plain"


def agora():
    return datetime.now(TZ)


def load():
    novo = not os.path.exists(DB)
    try:
        with open(DB, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {}
    d.setdefault("token", secrets.token_hex(8))
    d.setdefault("precos", {})
    d.setdefault("remetentes", ["M-PESA", "MPESA"])
    d.setdefault("limite", 10)
    d.setdefault("timeout", 300)
    d.setdefault("pedidos", [])
    if novo:
        save(d)
    return d


def save(d):
    with open(DB + ".tmp", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(DB + ".tmp", DB)


def valor(t):
    t = t.replace(" ", "")
    if "," in t and "." in t:
        dec = "," if t.rfind(",") > t.rfind(".") else "."
        t = t.replace("." if dec == "," else ",", "").replace(dec, ".")
    elif "," in t:
        a, b = t.rsplit(",", 1)
        t = a.replace(",", "") + ("." + b if len(b) == 2 else b)
    return Decimal(t)


def atual(d):
    return next((p for p in d["pedidos"] if p["estado"] == "EM_EXECUCAO"), None)


def feitos_hoje(d):
    h = agora().date().isoformat()
    return sum(1 for p in d["pedidos"] if p["estado"] in ("ENTREGUE", "EM_EXECUCAO") and (p.get("iniciado") or "").startswith(h))


def expirar(d):
    lim = agora() - timedelta(seconds=d["timeout"])
    for p in d["pedidos"]:
        if p["estado"] == "EM_EXECUCAO" and datetime.fromisoformat(p["iniciado"]) < lim:
            p["estado"] = "FALHA"
            p["nota"] = "sem confirmação a tempo; confirma o saldo antes de reenviar à mão"


def novo_sms(d, texto, rem):
    if d["remetentes"] and rem.strip().upper() not in [r.upper() for r in d["remetentes"]]:
        return 403, {"ok": False, "erro": "remetente não permitido: %r" % rem}
    m = RE_PAG.search(texto)
    if not m:
        return 200, {"ok": False, "ignorado": True, "erro": "não é SMS de recebimento M-Pesa"}
    pid, v, num = m.group(1).upper(), valor(m.group(2)), m.group(3)
    for p in d["pedidos"]:
        if p["id_mpesa"] == pid:
            return 200, {"ok": True, "duplicado": True, "id": p["id"], "estado": p["estado"]}
    mb = d["precos"].get(str(int(v))) if v == v.to_integral() else None
    p = {"id": len(d["pedidos"]) + 1, "id_mpesa": pid, "numero": num, "valor_mt": float(v), "mb": mb,
         "estado": "A_ENTREGAR" if mb else "REVISAO",
         "nota": "ok" if mb else "valor de %s MT não está na tabela de preços" % v,
         "criado": agora().isoformat(timespec="seconds"), "iniciado": None}
    d["pedidos"].append(p)
    return 200, {"ok": True, **p}


def proximo(d):
    if atual(d):
        return None, "em-execucao"
    if feitos_hoje(d) >= d["limite"]:
        return None, "limite-diario"
    for p in d["pedidos"]:
        if p["estado"] == "A_ENTREGAR":
            p["estado"], p["iniciado"] = "EM_EXECUCAO", agora().isoformat(timespec="seconds")
            return p, ""
    return None, "vazio"


def resultado(d, j, raw):
    p = next((x for x in d["pedidos"] if x["id"] == int(j["id"])), None) if j.get("id") else atual(d)
    if not p or p["estado"] != "EM_EXECUCAO":
        return 409, {"ok": False, "erro": "nenhum pedido em execução"}
    ok, t, m = j.get("ok"), raw.strip().lower(), RE_ENV.search(raw)
    if ok is None:
        if m:
            if m.group(2) != p["numero"][-9:] or int(m.group(1)) != p["mb"]:
                return 409, {"ok": False, "erro": "SMS não corresponde ao pedido em execução"}
            ok = True
        elif t in ("ok", "1", "true", "sim"):
            ok = True
        elif t in ("falha", "erro", "0", "false", "nao"):
            ok = False
        else:
            return 400, {"ok": False, "erro": "resultado não entendido"}
    p["estado"] = "ENTREGUE" if ok else "FALHA"
    p["nota"] = j.get("nota") or ("entregue" if ok else "falha reportada")
    return 200, {"ok": True, "id": p["id"], "estado": p["estado"]}


def api(d, met, rota, raw, h):
    try:
        j = json.loads(raw)
        j = j if isinstance(j, dict) else {}
    except Exception:
        j = {}
    if met == "POST" and rota == "/sms":
        t = j.get("texto") or j.get("sms") or j.get("text") or (raw if not j else "")
        c, r = novo_sms(d, t, h.get("x-remetente", ""))
        return c, r, J, {}
    if met == "GET" and rota == "/proximo-pedido":
        p, m = proximo(d)
        return (200, {"ok": True, "pedido": p}, J, {}) if p else (204, "", J, {"X-Motivo": m})
    if met == "POST" and rota == "/resultado":
        c, r = resultado(d, j, raw)
        return c, r, J, {}
    if met == "GET" and rota.startswith("/pedido-atual/"):
        p = atual(d)
        v = p and {"id": p["id"], "mb": p["mb"], "numero": p["numero"], "numero9": p["numero"][-9:]}.get(rota.split("/")[-1])
        return (200, str(v), T, {}) if v is not None and p else (404, "", T, {})
    if met == "GET" and rota == "/api/estado":
        return 200, {"pedidos": d["pedidos"][::-1], "precos": d["precos"], "remetentes": d["remetentes"],
                     "limite": d["limite"], "feitos_hoje": feitos_hoje(d)}, J, {}
    if met == "POST" and rota == "/api/config":
        if "precos" in j:
            d["precos"] = {str(int(float(k))): int(v) for k, v in j["precos"].items() if 100 <= int(v) <= 10240}
        if "remetentes" in j:
            d["remetentes"] = [str(x).strip() for x in j["remetentes"] if str(x).strip()]
        if "limite" in j:
            d["limite"] = max(1, min(10, int(j["limite"])))
        return 200, {"ok": True}, J, {}
    return 404, {"ok": False, "erro": "rota não encontrada", "rota": rota}, J, {}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def out(self, code, body, ctype=J, extra=None):
        if not isinstance(body, (str, bytes)):
            body = json.dumps(body, ensure_ascii=False)
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if code != 204:
            self.wfile.write(b)

    def handle_all(self, met):
        try:
            u = urlparse(self.path)
            q = parse_qs(u.query)
            rota = u.path.rstrip("/") or "/"
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n).decode("utf-8", "replace") if n else ""
            with LOCK:
                d = load()
                if met == "GET" and rota == "/":
                    with open(os.path.join(AQUI, "dashboard.html"), encoding="utf-8") as f:
                        return self.out(200, f.read().replace("__TOKEN__", d["token"]), "text/html")
                tok = self.headers.get("x-token") or q.get("token", [""])[0]
                if not secrets.compare_digest(tok.encode(), d["token"].encode()):
                    return self.out(401, {"ok": False, "erro": "token inválido"})
                expirar(d)
                c, r, ct, ex = api(d, met, rota, raw, self.headers)
                save(d)
            self.out(c, r, ct, ex)
        except Exception as e:
            self.out(500, {"ok": False, "erro": str(e)})

    def do_GET(self):
        self.handle_all("GET")

    def do_POST(self):
        self.handle_all("POST")


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
