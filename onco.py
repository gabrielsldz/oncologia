#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Consulta unificada ao Painel Oncológico (DATASUS)

Função principal
----------------
consulta_onco(
    ano: int,
    *,
    sexo: str = "ALL",               # "ALL", "M" ou "F"
    faixa_etaria: str | None = None, # rótulo exato de AGE_GROUPS
    cid: str | None = None,          # código CID detalhado (ex.: "C50")
    regiao: str | None = None,       # "Norte", "Nordeste", "Sudeste", "Sul", "Centro-Oeste"
    paralelo: bool = False,
    max_workers: int = 12,
) -> dict | str | None

Regras de escolha
-----------------
1) Se ``cid``           → diagnóstico detalhado
2) Se ``faixa_etaria``  → faixa etária
3) Caso contrário       → totais por região, filtrando por ``sexo``:
   •  "ALL" → total (sexo agregado)
   •  "M"   → apenas masculino
   •  "F"   → apenas feminino
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict

import requests

# ----------------------------------------------------------------------
# Sessão HTTP (cookie + keep-alive)
# ----------------------------------------------------------------------
URL_POST   = "http://tabnet.datasus.gov.br/cgi/webtabx.exe?PAINEL_ONCO/PAINEL_ONCOLOGIABR.def"
URL_COOKIE = "http://tabnet.datasus.gov.br/cgi/dhdat.exe?PAINEL_ONCO/PAINEL_ONCOLOGIABR.def"
PARAMS     = {"PAINEL_ONCO/PAINEL_ONCOLOGIABR.def": ""}

HEADERS = {
    "Host":                     "tabnet.datasus.gov.br",
    "Proxy-Connection":         "keep-alive",
    "Cache-Control":            "max-age=0",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent":               "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Origin":                   "http://tabnet.datasus.gov.br",
    "Content-Type":             "application/x-www-form-urlencoded",
    "Accept":                   "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer":                  URL_COOKIE,
    "Accept-Encoding":          "gzip, deflate",
    "Accept-Language":          "pt-BR,pt;q=0.9",
}

_SESSION = requests.Session()
_SESSION.headers.update(HEADERS)
_SESSION.get(URL_COOKIE, params=PARAMS, timeout=30)          # cookie obrigatório

# ----------------------------------------------------------------------
# Constantes & regex
# ----------------------------------------------------------------------
REGIONS = {1: "Norte", 2: "Nordeste", 3: "Sudeste", 4: "Sul", 5: "Centro-Oeste"}

_SEXPARAM = {
    "ALL": "TODAS_AS_CATEGORIAS__",
    "M":   "Masculino%7CM%7C1",
    "F":   "Feminino%7CF%7C1",
}

_RE_ADDROWS = re.compile(r"data\.addRows\(\s*\[(.*?)\]\s*\);", re.DOTALL)
_RE_LINHA   = re.compile(
    r"\[\s*['\"]\s*(\d+)\s+Regi(?:ão|ao)\s+[^\]]+?['\"]\s*,\s*\{v:\s*([\d\.]+)"
)

# ----------------------------------------------------------------------
# Helpers HTTP
# ----------------------------------------------------------------------
def _extrair_addrows(html: str) -> str:
    m = _RE_ADDROWS.search(html)
    return m.group(1).strip() if m else ""

def _post(payload: str) -> str:
    r = _SESSION.post(URL_POST, params=PARAMS, data=payload, timeout=30)
    r.raise_for_status()
    return r.text

def _linhas_para_dict(bloco: str) -> Dict[int, float]:
    return {int(cod): float(v) for cod, v in _RE_LINHA.findall(bloco)}

# ----------------------------------------------------------------------
# Payloads – região / faixa etária / diagnóstico detalhado
# ----------------------------------------------------------------------
def _payload_regioes(ano: int, sexo_param: str) -> str:
    return (
        "Linha=Regi%E3o+-+resid%EAncia%7CSUBSTR%28CO_MUNICIPIO_RESIDENCIA%2C1%2C1%29%7C1"
        "%7Cterritorio%5Cbr_regiao.cnv"
        "&Coluna=--N%E3o-Ativa--"
        "&Incremento=Casos%7C%3D+count%28*%29"
        f"&PAno+do+diagn%F3stico={ano}%7C{ano}%7C4"
        "&XRegi%E3o+-+resid%EAncia=TODAS_AS_CATEGORIAS__"
        "&XRegi%E3o+-+diagn%F3stico=TODAS_AS_CATEGORIAS__"
        "&XRegi%E3o+-+tratamento=TODAS_AS_CATEGORIAS__"
        "&XUF+da+resid%EAncia=TODAS_AS_CATEGORIAS__"
        "&XUF+do+diagn%F3stico=TODAS_AS_CATEGORIAS__"
        "&XUF+do+tratamento=TODAS_AS_CATEGORIAS__"
        "&SRegi%E3o+de+Saude+-+resid%EAncia=TODAS_AS_CATEGORIAS__"
        "&SRegi%E3o+de+Saude+-+diagn%F3stico=TODAS_AS_CATEGORIAS__"
        "&SRegi%E3o+de+Saude+-+tratamento=TODAS_AS_CATEGORIAS__"
        "&SMunic%ED%ADpio+da+resid%EAncia=TODAS_AS_CATEGORIAS__"
        "&SMunic%ED%ADpio+do+diagn%F3stico=TODAS_AS_CATEGORIAS__"
        "&SMunic%ED%ADpio+do+tratamento=TODAS_AS_CATEGORIAS__"
        "&XDiagn%F3stico=TODAS_AS_CATEGORIAS__"
        "&XDiagn%F3stico+Detalhado=TODAS_AS_CATEGORIAS__"
        f"&XSexo={sexo_param}"
        "&XFaixa+et%E1ria=TODAS_AS_CATEGORIAS__"
        "&XIdade=TODAS_AS_CATEGORIAS__"
        "&XM%EAs%2FAno+do+diagn%F3stico=TODAS_AS_CATEGORIAS__"
        "&SAno+do+tratamento=TODAS_AS_CATEGORIAS__"
        "&XM%EAs%2FAno+do+tratamento=TODAS_AS_CATEGORIAS__"
        "&XModalidade+Terap%EAutica=TODAS_AS_CATEGORIAS__"
        "&XEstadiamento=TODAS_AS_CATEGORIAS__"
        "&XTempo+Tratamento=TODAS_AS_CATEGORIAS__"
        "&XTempo+Tratamento+%28detalhado%29=TODAS_AS_CATEGORIAS__"
        "&XEstabelecimento+de+tratamento=TODAS_AS_CATEGORIAS__"
        "&XEstabelecimento+diagn%F3stico=TODAS_AS_CATEGORIAS__"
        "&nomedef=PAINEL_ONCO%2FPAINEL_ONCOLOGIABR.def"
        "&grafico="
    )

AGE_GROUPS = {
    "0 a 19 anos":    "0+a+19+anos%7C000-019%7C3",
    "20 a 24 anos":   "20+a+24+anos%7C020-024%7C3",
    "25 a 29 anos":   "25+a+29+anos%7C025-029%7C3",
    "30 a 34 anos":   "30+a+34+anos%7C030-034%7C3",
    "35 a 39 anos":   "35+a+39+anos%7C035-039%7C3",
    "40 a 44 anos":   "40+a+44+anos%7C040-044%7C3",
    "45 a 49 anos":   "45+a+49+anos%7C045-049%7C3",
    "50 a 54 anos":   "50+a+54+anos%7C050-054%7C3",
    "55 a 59 anos":   "55+a+59+anos%7C055-059%7C3",
    "60 a 64 anos":   "60+a+64+anos%7C060-064%7C3",
    "65 a 69 anos":   "65+a+69+anos%7C065-069%7C3",
    "70 a 74 anos":   "70+a+74+anos%7C070-074%7C3",
    "75 a 79 anos":   "75+a+79+anos%7C075-079%7C3",
    "80 anos e mais": "80+anos+e+mais%7C080-999%7C3",
}

def _payload_faixa_etaria(ano: int, age_val: str, sexo_param: str) -> str:
    return (
        "Linha=Regi%E3o+-+resid%EAncia%7CSUBSTR%28CO_MUNICIPIO_RESIDENCIA%2C1%2C1%29%7C1"
        "%7Cterritorio%5Cbr_regiao.cnv"
        "&Coluna=--N%E3o-Ativa--"
        "&Incremento=Casos%7C%3D+count%28*%29"
        f"&PAno+do+diagn%F3stico={ano}%7C{ano}%7C4"
        "&XRegi%E3o+-+resid%EAncia=TODAS_AS_CATEGORIAS__"
        "&XRegi%E3o+-+diagn%F3stico=TODAS_AS_CATEGORIAS__"
        "&XRegi%E3o+-+tratamento=TODAS_AS_CATEGORIAS__"
        "&XUF+da+resid%EAncia=TODAS_AS_CATEGORIAS__"
        "&XUF+do+diagn%F3stico=TODAS_AS_CATEGORIAS__"
        "&XUF+do+tratamento=TODAS_AS_CATEGORIAS__"
        "&SRegi%E3o+de+Saude+-+resid%EAncia=TODAS_AS_CATEGORIAS__"
        "&SRegi%E3o+de+Saude+-+diagn%F3stico=TODAS_AS_CATEGORIAS__"
        "&SRegi%E3o+de+Saude+-+tratamento=TODAS_AS_CATEGORIAS__"
        "&SMunic%ED%ADpio+da+resid%EAncia=TODAS_AS_CATEGORIAS__"
        "&SMunic%ED%ADpio+do+diagn%F3stico=TODAS_AS_CATEGORIAS__"
        "&SMunic%ED%ADpio+do+tratamento=TODAS_AS_CATEGORIAS__"
        "&XDiagn%F3stico=TODAS_AS_CATEGORIAS__"
        "&XDiagn%F3stico+Detalhado=TODAS_AS_CATEGORIAS__"
        f"&XSexo={sexo_param}"
        f"&XFaixa+et%E1ria={age_val}"
        "&XIdade=TODAS_AS_CATEGORIAS__"
        "&XM%EAs%2FAno+do+diagn%F3stico=TODAS_AS_CATEGORIAS__"
        "&SAno+do+tratamento=TODAS_AS_CATEGORIAS__"
        "&XM%EAs%2FAno+do+tratamento=TODAS_AS_CATEGORIAS__"
        "&XModalidade+Terap%EAutica=TODAS_AS_CATEGORIAS__"
        "&XEstadiamento=TODAS_AS_CATEGORIAS__"
        "&XTempo+Tratamento=TODAS_AS_CATEGORIAS__"
        "&XTempo+Tratamento+%28detalhado%29=TODAS_AS_CATEGORIAS__"
        "&XEstabelecimento+de+tratamento=TODAS_AS_CATEGORIAS__"
        "&XEstabelecimento+diagn%F3stico=TODAS_AS_CATEGORIAS__"
        "&nomedef=PAINEL_ONCO%2FPAINEL_ONCOLOGIABR.def"
        "&grafico="
    )

# --- lista completa de CIDs ---------------------------------------------------
CODES_DETALHADOS = (
    [f"C{n:02d}" for n in range(0, 17)]
    + [f"C{n:02d}" for n in range(17, 27)]
    + [f"C{n:02d}" for n in (30, 31, 32, 33, 34, 37, 38, 39)]
    + [f"C{n:02d}" for n in (40, 41, 43, 44, 45, 46, 47, 48, 49)]
    + [f"C{n:02d}" for n in range(50, 59)]
    + [f"C{n:02d}" for n in range(60, 70)]
    + [f"C{n:02d}" for n in range(70, 79)]
    + [
        "C79", "C80", "C81", "C82", "C83", "C84", "C85", "C88",
        "C90", "C91", "C92", "C93", "C94", "C95", "C96", "C97",
    ]
    + [f"D{n:02d}" for n in range(0, 8) if n != 8] + ["D09"]
    + [f"D{n:02d}" for n in range(37, 49)]
)

def _payload_diag_detalhado(ano: int, code: str, sexo_param: str) -> str:
    base = (
        "Linha=Regi%E3o+-+resid%EAncia%7CSUBSTR%28CO_MUNICIPIO_RESIDENCIA%2C1%2C1%29%7C1"
        "%7Cterritorio%5Cbr_regiao.cnv"
        "&Coluna=--N%E3o-Ativa--"
        "&Incremento=Casos%7C%3D+count%28*%29"
        f"&PAno+do+diagn%F3stico={ano}%7C{ano}%7C4"
        "&XRegi%E3o+-+resid%EAncia=TODAS_AS_CATEGORIAS__"
        "&XRegi%E3o+-+diagn%F3stico=TODAS_AS_CATEGORIAS__"
        "&XRegi%E3o+-+tratamento=TODAS_AS_CATEGORIAS__"
        "&XUF+da+resid%EAncia=TODAS_AS_CATEGORIAS__"
        "&XUF+do+diagn%F3stico=TODAS_AS_CATEGORIAS__"
        "&XUF+do+tratamento=TODAS_AS_CATEGORIAS__"
        "&SRegi%E3o+de+Saude+-+resid%EAncia=TODAS_AS_CATEGORIAS__"
        "&SRegi%E3o+de+Saude+-+diagn%F3stico=TODAS_AS_CATEGORIAS__"
        "&SRegi%E3o+de+Saude+-+tratamento=TODAS_AS_CATEGORIAS__"
        "&SMunic%ED%ADpio+da+resid%EAncia=TODAS_AS_CATEGORIAS__"
        "&SMunic%ED%ADpio+do+diagn%F3stico=TODAS_AS_CATEGORIAS__"
        "&SMunic%ED%ADpio+do+tratamento=TODAS_AS_CATEGORIAS__"
        "&XDiagn%F3stico=TODAS_AS_CATEGORIAS__"
        "&XDiagn%F3stico+Detalhado=C00+-+Neoplasia+maligna%7CC00%7C3"
        f"&XSexo={sexo_param}"
        "&XFaixa+et%E1ria=TODAS_AS_CATEGORIAS__"
        "&XIdade=TODAS_AS_CATEGORIAS__"
        "&XM%EAs%2FAno+do+diagn%F3stico=TODAS_AS_CATEGORIAS__"
        "&SAno+do+tratamento=TODAS_AS_CATEGORIAS__"
        "&XM%EAs%2FAno+do+tratamento=TODAS_AS_CATEGORIAS__"
        "&XModalidade+Terap%EAutica=TODAS_AS_CATEGORIAS__"
        "&XEstadiamento=TODAS_AS_CATEGORIAS__"
        "&XTempo+Tratamento=TODAS_AS_CATEGORIAS__"
        "&XTempo+Tratamento+%28detalhado%29=TODAS_AS_CATEGORIAS__"
        "&XEstabelecimento+de+tratamento=TODAS_AS_CATEGORIAS__"
        "&XEstabelecimento+diagn%F3stico=TODAS_AS_CATEGORIAS__"
        "&nomedef=PAINEL_ONCO%2FPAINEL_ONCOLOGIABR.def"
        "&grafico="
    )
    return (
        re.sub(r"%7CC00%7C3", f"%7C{code}%7C3", base, count=1)
        .replace("C00+-+Neoplasia+maligna", f"{code}")
    )

# ----------------------------------------------------------------------
# Funções de camada baixa
# ----------------------------------------------------------------------
def _totais_por_regiao(ano: int, sexo: str) -> Dict[str, Dict[str, float | str]]:
    """
    Retorna somente um sexo:
      • sexo = "ALL"  → valores M+F
      • sexo = "M"    → apenas masculino
      • sexo = "F"    → apenas feminino
    """
    html    = _post(_payload_regioes(ano, _SEXPARAM[sexo]))
    valores = _linhas_para_dict(_extrair_addrows(html))      # já vem só do sexo pedido
    total   = sum(valores.values())
    res = {REGIONS[cod]: {"v": v, "f": f"{v:,.0f}".replace(",", ".")}
           for cod, v in valores.items()}
    res[" Total"] = {"v": total, "f": f"{total:,.0f}".replace(",", ".")}
    return res

def _dados_por_faixa_etaria(
    ano: int, sexo: str, faixa_label: str | None, paralelo: bool, max_workers: int
) -> Dict[str, str | None]:
    if faixa_label:
        html = _post(_payload_faixa_etaria(ano, AGE_GROUPS[faixa_label], _SEXPARAM[sexo]))
        return {faixa_label: _extrair_addrows(html) if "Nenhum registro" not in html else None}

    resultados: Dict[str, str | None] = {}

    def _worker(label: str, val: str) -> tuple[str, str | None]:
        h = _post(_payload_faixa_etaria(ano, val, _SEXPARAM[sexo]))
        return label, _extrair_addrows(h) if "Nenhum registro" not in h else None

    if not paralelo:
        for lbl, val in AGE_GROUPS.items():
            resultados[lbl] = _worker(lbl, val)[1]
        return resultados

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(_worker, l, v) for l, v in AGE_GROUPS.items()]
        for f in as_completed(futs):
            lbl, bloco = f.result()
            resultados[lbl] = bloco
    return resultados

def _dados_por_diag_detalhado(
    ano: int, sexo: str, cid_code: str | None, paralelo: bool, max_workers: int
) -> Dict[str, str | None]:
    if cid_code:
        html = _post(_payload_diag_detalhado(ano, cid_code, _SEXPARAM[sexo]))
        return {cid_code: _extrair_addrows(html) if "Nenhum registro" not in html else None}

    resultados: Dict[str, str | None] = {}

    def _worker(code: str) -> tuple[str, str | None]:
        h = _post(_payload_diag_detalhado(ano, code, _SEXPARAM[sexo]))
        return code, _extrair_addrows(h) if "Nenhum registro" not in h else None

    if not paralelo:
        for code in CODES_DETALHADOS:
            resultados[code] = _worker(code)[1]
        return resultados

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(_worker, c) for c in CODES_DETALHADOS]
        for f in as_completed(futs):
            code, bloco = f.result()
            resultados[code] = bloco
    return resultados

# ----------------------------------------------------------------------
# FUNÇÃO PÚBLICA
# ----------------------------------------------------------------------
def consulta_onco(
    ano: int,
    *,
    sexo: str = "ALL",
    faixa_etaria: str | None = None,
    cid: str | None = None,
    regiao: str | None = None,
    paralelo: bool = False,
    max_workers: int = 12,
) -> dict | str | None:
    """
    Consulta unificada ao painel oncológico (ver docstring do módulo).
    """
    sexo = sexo.upper()
    if sexo not in _SEXPARAM:
        raise ValueError("sexo deve ser 'ALL', 'M' ou 'F'")

    # 1) Diagnóstico detalhado -----------------------------------------
    if cid is not None:
        return _dados_por_diag_detalhado(
            ano, sexo, cid, paralelo=paralelo, max_workers=max_workers
        )

    # 2) Faixa etária ---------------------------------------------------
    if faixa_etaria is not None:
        if faixa_etaria not in AGE_GROUPS:
            raise ValueError("faixa_etaria inválida – veja AGE_GROUPS.keys()")
        return _dados_por_faixa_etaria(
            ano, sexo, faixa_etaria, paralelo=paralelo, max_workers=max_workers
        )

    # 3) Totais por região (com sexo filtrado) --------------------------
    dados = _totais_por_regiao(ano, sexo)

    # filtro de região, se solicitado
    if regiao:
        if regiao not in REGIONS.values():
            raise ValueError(f"regiao inválida. Opções: {list(REGIONS.values())}")
        return {regiao: dados[regiao], " Total": dados[" Total"]}
    return dados

# ----------------------------------------------------------------------
# Teste rápido
#parametros = ano, sexo, faixa_etaria, cid, regiao, paralelo, max_workers
# ----------------------------------------------------------------------
if __name__ == "__main__":
    from time import perf_counter

    ANO = 2021

    t0 = perf_counter()
    print("# Totais – sexo agregado (ALL)")
    print(consulta_onco(ANO))
    print(f"{perf_counter() - t0:.2f}s\n")

    print("# Totais – apenas Masculino")
    print(consulta_onco(ANO, sexo="M"))

    print("\n# Faixa 25-29 anos – Feminino")
    print(consulta_onco(ANO, sexo="F", faixa_etaria="25 a 29 anos"))

    print("\n# CID C50 – Masculino")
    print(consulta_onco(ANO, cid="C50", sexo="M"))

    print("\n# Sudeste – Agregado")
    print(consulta_onco(ANO, regiao="Sudeste"))
