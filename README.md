# 🩺 Painel Oncológico (DATASUS)

![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python)
![Status](https://img.shields.io/badge/status-alpha-orange)


Consulta, visualização e **download de dados oncológicos (câncer) do DATASUS** de forma simples, usando apenas Python.

O repositório contém dois arquivos principais:

| Arquivo       | Descrição                                                                                                          |
| ------------- | ------------------------------------------------------------------------------------------------------------------ |
| **`onco.py`** | *Wrapper* de alto nível que faz *scraping* do Painel Oncológico (2013 – 2025) e devolve resultados em dicionários. |
| **`app.py`**  | Aplicação [Streamlit](https://streamlit.io/) pronta para uso, com filtros e gráficos interativos.                  |

> **Por quê?**
> A interface Web oficial não é amigável para automação. Este projeto abstrai sessões, payloads e parsing de HTML para você focar na análise.

---

## ✨ Principais funcionalidades

| Função              | O que faz                                                               | Exemplo                                                   |
| ------------------- | ----------------------------------------------------------------------- | --------------------------------------------------------- |
| `consulta_onco`     | Consulta unificada (por região, sexo, faixa etária ou CID detalhado)    | `python<br>consulta_onco(2023, sexo="F", regiao="Sul")`   |
| Modo paralelo       | *Scraping* multi-thread (até 32 threads)                                | `python<br>consulta_onco(2024, cid="C50", paralelo=True)` |
| Interface Streamlit | Heatmap de intervalos, comparação lado-a-lado, filtros na barra lateral | `bash<br>streamlit run app.py`                            |

---

## 📦 Instalação

```bash
# clone o repositório
git clone https://github.com/<seu-usuario>/painel-onco.git
cd painel-onco

# (opcional) crie um ambiente virtual
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# dependências
pip install -r requirements.txt
```

<details>
<summary><code>requirements.txt</code></summary>

```
requests
streamlit
pandas
matplotlib
seaborn
```

</details>

---

## 🚀 Uso rápido

### Biblioteca (`onco.py`)

```python
from onco import consulta_onco

# Total agregado (M + F) por região em 2023
print(consulta_onco(2023))

# Casos masculinos na região Sudeste
print(consulta_onco(2022, sexo="M", regiao="Sudeste"))

# Faixa etária 25–29 anos, feminino
print(consulta_onco(2021, sexo="F", faixa_etaria="25 a 29 anos"))

# CID detalhado C50, em paralelo
print(consulta_onco(2024, cid="C50", paralelo=True, max_workers=16))
```

Saída típica:

```text
{
  'Norte':        {'v': 2_345, 'f': '2.345'},
  'Nordeste':     {'v': 7_890, 'f': '7.890'},
  'Sudeste':      {'v': 15_432, 'f': '15.432'},
  'Sul':          {'v': 6_321, 'f': '6.321'},
  'Centro-Oeste': {'v': 2_987, 'f': '2.987'},
  ' Total':       {'v': 34_975, 'f': '34.975'}
}
```

### Interface gráfica (Streamlit)

```bash
streamlit run app.py
```

1. Ajuste **Sexo**, **Faixa etária**, **CID** e **Região** na barra lateral.
2. Escolha o **Modo de consulta**:

    * **Simples** – único ano
    * **Intervalo de anos** – gera heatmap + totais por ano
    * **Comparar várias consultas** – barras lado a lado
3. Clique em **Consultar** e explore!

---

## ⚙️ Parâmetros da função `consulta_onco`

| Parâmetro      | Tipo            | Padrão  | Descrição                                |
| -------------- | --------------- | ------- | ---------------------------------------- |
| `ano`          | `int`           | –       | Ano do diagnóstico (2013 – 2025)         |
| `sexo`         | `str`           | `"ALL"` | `"ALL"`, `"M"` (masc), `"F"` (fem)       |
| `faixa_etaria` | `str` ou `None` | `None`  | Chaves de `AGE_GROUPS`                   |
| `cid`          | `str` ou `None` | `None`  | Código CID detalhado (ex. `"C50"`)       |
| `regiao`       | `str` ou `None` | `None`  | `"Norte"`, `"Sudeste"`, etc.             |
| `paralelo`     | `bool`          | `False` | Ativa *ThreadPoolExecutor*               |
| `max_workers`  | `int`           | `12`    | Número de threads quando `paralelo=True` |

---

## 📈 Roadmap

* [ ] **Dump completo** de todos os anos & CIDs para banco local
* [ ] Rotina de **atualização automática** (cron + SQLite/PostgreSQL)

---

## 🤝 Contribuindo

1. **Fork** → 2. **Branch** → 3. **Pull Request**
   Siga a [PEP 8](https://peps.python.org/pep-0008/) e inclua testes sempre que possível.
