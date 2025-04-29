# app.py ---------------------------------------------------------------
import re
from pathlib import Path

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pandas.api.types import is_numeric_dtype

from onco import consulta_onco, AGE_GROUPS, REGIONS

# ╭──────────────────────── 1.  Lê tipos.txt ─────────────────────────╮
TIPOS_TXT = Path(__file__).with_name("tipos.txt")         # mesmo diretório
CID_NOMES: dict[str, str] = {}
if TIPOS_TXT.exists():
    _rx = re.compile(r"^([CD]\d{2})\s+[\u2013-]\s+(.*)$")   # C00 – Descrição
    with TIPOS_TXT.open(encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            m = _rx.match(ln)
            if m:
                CID_NOMES[m.group(1)] = m.group(2)

CODES_LIST = [f"{c} – {CID_NOMES[c]}" for c in CID_NOMES]     # para dropdown
# ╰────────────────────────────────────────────────────────────────────╯

# ╭───────────────────── 2.  Configuração geral ──────────────────────╮
st.set_page_config("Painel Oncológico", "🩺", layout="wide")
st.markdown(
    """
    <style>
      .main  {background:#F4F7FA;}
      div[data-testid="stSidebar"] {background:#263238;color:#fff;}
      h1,h2,h3 {color:#263238;}
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("🩺 Painel Oncológico (DATASUS)")
# ╰────────────────────────────────────────────────────────────────────╯

# ╭────────────────────────── 3.  Regex addRows ───────────────────────╮
_RE_ADDROW_NUM = re.compile(r'"\d+\s+Regi(?:ão|ao)\s+([^"]+)"\s*,\s*\{v:\s*([\d\.]+)')
_RE_TOTAL_NUM  = re.compile(r"' Total'\s*,\s*\{v:\s*([\d\.]+)")
def _parse_addrows(raw: str) -> dict[str, float]:
    out: dict[str, float] = {reg: float(val) for reg, val in _RE_ADDROW_NUM.findall(raw)}
    m = _RE_TOTAL_NUM.search(raw)
    if m:
        out[" Total"] = float(m.group(1))
    return out
# ╰────────────────────────────────────────────────────────────────────╯

# ╭──────────────────── 4.  Funções utilitárias ──────────────────────╮
def dict_to_df(d: dict) -> pd.DataFrame:
    if not isinstance(d, dict):
        return pd.DataFrame({"Valor": [d]})

    # 1) {"região": {"v": ...}}
    if all(isinstance(v, dict) and "v" in v for v in d.values()):
        base = {k.lstrip(): v["v"] for k, v in d.items()}
        return pd.Series(base, name="Casos").to_frame()

    # 2) {"chave": "addRows[...]"}
    if all(isinstance(v, (str, type(None))) for v in d.values()):
        raw = next((v for v in d.values() if v), "")
        return pd.Series(_parse_addrows(raw), name="Casos").to_frame()

    return pd.DataFrame.from_dict(d, orient="index")


def filter_by_region(df: pd.DataFrame, regiao: str | None) -> pd.DataFrame:
    if regiao:
        keep = [r for r in [regiao, " Total"] if r in df.index]
        return df.loc[keep] if keep else df
    return df.loc[[" Total"]] if " Total" in df.index else df


def show_df(df: pd.DataFrame):
    fmt = {c: "{:,.0f}".format for c in df.columns if is_numeric_dtype(df[c])}
    st.dataframe(df.style.format(fmt))


def barplot(df: pd.DataFrame, title: str):
    numeric = [c for c in df.columns if is_numeric_dtype(df[c])]
    if not numeric or df.empty:
        st.info("Nenhuma coluna numérica para plotar.")
        return
    fig, ax = plt.subplots()
    df[numeric].plot(kind="bar", ax=ax, legend=False)
    ax.set_title(title)
    ax.set_ylabel("Casos")
    st.pyplot(fig)


def heatmap(df: pd.DataFrame, title: str):
    fig, ax = plt.subplots()
    sns.heatmap(df, annot=True, fmt=".0f", cmap="YlOrRd", ax=ax)
    ax.set_title(title)
    st.pyplot(fig)
# ╰────────────────────────────────────────────────────────────────────╯

# ╭──────────────────── 5.  Sidebar - parâmetros base ─────────────────╮
st.sidebar.header("Parâmetros base")

sexo    = st.sidebar.selectbox("Sexo", ["ALL", "M", "F"])
faixa   = st.sidebar.selectbox("Faixa etária", [""] + list(AGE_GROUPS.keys()))
cid_raw = st.sidebar.selectbox("CID detalhado", [""] + CODES_LIST)
regiao  = st.sidebar.selectbox("Região", [""] + list(REGIONS.values()))
paral   = st.sidebar.checkbox("Modo paralelo")
workers = st.sidebar.slider("Threads", 1, 32, 12)

cid_code = cid_raw.split(" –")[0] if cid_raw else ""

common_kwargs = dict(
    sexo=sexo,
    faixa_etaria=faixa or None,
    cid=cid_code or None,
    regiao=None,         # filtramos depois
    paralelo=paral,
    max_workers=workers,
)
# ╰────────────────────────────────────────────────────────────────────╯

# ╭────────────────── 6.  Escolha do modo de operação ─────────────────╮
modo = st.radio(
    "Modo de consulta",
    ["Simples", "Intervalo de anos", "Comparar várias consultas"],
    horizontal=True,
)
# ╰────────────────────────────────────────────────────────────────────╯

# ╭────────────────────────── 7.  Modo Simples ────────────────────────╮
if modo == "Simples":
    ano = st.number_input("Ano", 2008, 2025, 2023, 1)
    if st.button("🔎 Consultar"):
        with st.spinner("Buscando…"):
            data = consulta_onco(ano, **common_kwargs)
        df = filter_by_region(dict_to_df(data), regiao or None)
        show_df(df)
        barplot(df, f"Casos – {ano}")
# ╰────────────────────────────────────────────────────────────────────╯

# ╭────────────────────── 8.  Intervalo de anos ───────────────────────╮
elif modo == "Intervalo de anos":
    c1, c2 = st.columns(2)
    with c1:
        ano_ini = st.number_input("Ano inicial", 2008, 2025, 2019, 1)
    with c2:
        ano_fim = st.number_input("Ano final", 2008, 2025, 2023, 1)

    if ano_fim < ano_ini:
        st.error("Ano final deve ser ≥ Ano inicial")
    elif st.button("📈 Gerar intervalo"):
        dfs = {}
        with st.spinner("Coletando dados…"):
            for yr in range(ano_ini, ano_fim + 1):
                res = consulta_onco(yr, **common_kwargs)
                s = filter_by_region(dict_to_df(res), regiao or None).iloc[:, 0]
                dfs[yr] = s
        df_int = pd.DataFrame(dfs).T
        show_df(df_int)
        if not df_int.empty and all(is_numeric_dtype(df_int[c]) for c in df_int):
            heatmap(df_int.T, f"{ano_ini}–{ano_fim}")
            barplot(df_int.sum(axis=1).to_frame("Total"), "Total por ano")
# ╰────────────────────────────────────────────────────────────────────╯

# ╭────────────── 9.  Comparar N (2–10) consultas dinamicamente ───────╮
else:
    n_cons = st.slider("Número de consultas a comparar", 2, 10, 2, 1)
    consultas = []
    for i in range(n_cons):
        st.markdown(f"#### Consulta {i+1}")
        col1, col2 = st.columns(2)
        with col1:
            year = st.number_input(f"Ano {i+1}", 2008, 2025, 2023 - i, 1, key=f"yr{i}")
        with col2:
            sx = st.selectbox(f"Sexo {i+1}", ["ALL", "M", "F"], key=f"sx{i}")
        consultas.append((year, sx))
        st.divider()

    if st.button("🔀 Comparar"):
        col_dict = {}
        with st.spinner("Consultando…"):
            for idx, (yr, sx) in enumerate(consultas, 1):
                res = consulta_onco(yr, **{**common_kwargs, "sexo": sx})
                s = filter_by_region(dict_to_df(res), regiao or None).iloc[:, 0]
                label = f"{idx}) {yr}-{sx}"
                col_dict[label] = s
        df_cmp = pd.DataFrame(col_dict)
        show_df(df_cmp)

        if not df_cmp.empty and all(is_numeric_dtype(df_cmp[c]) for c in df_cmp):
            st.subheader("Barras lado a lado")
            fig, ax = plt.subplots()
            width = 0.8 / n_cons
            x = range(len(df_cmp))
            for j, col in enumerate(df_cmp.columns):
                ax.bar([i - 0.4 + width/2 + j*width for i in x],
                       df_cmp[col], width, label=col)
            ax.set_xticks(x, df_cmp.index, rotation=45)
            ax.set_ylabel("Casos")
            ax.legend()
            st.pyplot(fig)
# ╰────────────────────────────────────────────────────────────────────╯
