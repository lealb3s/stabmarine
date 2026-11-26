"""Leitura de cotas em metros, incluindo a aba Tabela de trabalho da AP1."""

from io import BytesIO, StringIO
import csv
from pathlib import Path
from collections import Counter
import re
import unicodedata
import pandas as pd
import numpy as np


def norm(s):
    return (
        unicodedata.normalize("NFKD", str(s))
        .encode("ascii", "ignore")
        .decode()
        .lower()
        .strip()
    )


EXCEL = ["xlsx", "xls", "xlsm", "xlsb", "xltx", "xltm", "xlt", "ods"]
TEXTOS = ["csv", "tsv", "txt"]
COLUNAS = ["x_m", "z_m", "meia_boca_m"]
UNIDADES = {"m": 1.0, "cm": 0.01, "mm": 0.001, "ft": 0.3048, "in": 0.0254}


def excel(nome):
    return Path(nome).suffix.lower()[1:] in EXCEL


def abrir_livro(data):
    try:
        return pd.ExcelFile(BytesIO(data), engine="calamine")
    except Exception as exc:
        raise ValueError(
            "Não foi possível abrir a pasta de trabalho. Para arquivos protegidos, salve uma cópia sem senha. Se necessário, regrave em XLSX no Excel."
        ) from exc


def abas(data, nome):
    if not excel(nome):
        return []
    with abrir_livro(data) as xl:
        return xl.sheet_names


def bruto(data, nome, aba=None):
    if excel(nome):
        with abrir_livro(data) as xl:
            aba = aba or next(
                (n for n in xl.sheet_names if norm(n) == "tabela de trabalho"),
                xl.sheet_names[0],
            )
            try:
                return xl.parse(aba, header=None, dtype=object)
            except Exception as exc:
                raise ValueError(
                    f"Não foi possível ler os valores da aba {aba}."
                ) from exc
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        txt = data.decode("utf-16")
    else:
        try:
            txt = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            txt = data.decode("cp1252")

    def score(delim):
        counts = Counter(
            len(row)
            for row in csv.reader(txt.splitlines()[:150], delimiter=delim)
            if len(row) > 1
        )
        return max(counts.values(), default=0)

    sep = max([";", "\t", ",", "|"], key=score)
    rows = list(csv.reader(StringIO(txt), delimiter=sep))
    return pd.DataFrame(rows).replace(r"^\s*$", np.nan, regex=True)


def numero(v):
    if pd.isna(v):
        raise ValueError("célula vazia")
    s = str(v).strip().replace("−", "-").replace("\xa0", "").replace(" ", "")
    if "," in s and "." in s:
        milhar = "." if s.rfind(",") > s.rfind(".") else ","
        s = s.replace(milhar, "")
    n = float(s.replace(",", "."))
    if not np.isfinite(n):
        raise ValueError("valor não finito")
    return n


def cotas(data, nome, aba=None):
    return automatico(bruto(data, nome, aba))


def automatico(raw):
    df = raw.dropna(how="all").reset_index(drop=True)
    for i, linha in df.iterrows():
        rot = [norm(v) for v in linha]
        if {"x_m", "z_m", "meia_boca_m"} <= set(rot):
            out = df.iloc[
                i + 1 :, [rot.index(k) for k in ["x_m", "z_m", "meia_boca_m"]]
            ].copy()
            out.columns = ["x_m", "z_m", "meia_boca_m"]
            return out.map(numero).reset_index(drop=True)
        if len(rot) >= 3 and rot[1] in ["x", "x_m", "x (m)"]:
            valid = [
                j for j, s in enumerate(rot[2:], 2) if s.startswith(("wl", "la", "bl"))
            ]
            if len(valid) < 2:
                continue
            begin = i + 1
            if pd.isna(df.iloc[begin, 1]) or pd.isna(df.iloc[begin, 0]):
                alturas = [numero(df.iloc[begin, j]) for j in valid]
                begin += 1
            else:
                alturas = []
                for j in valid:
                    token = rot[j]
                    m = re.search(r"(?:z\s*=\s*|la[_ ])(-?\d+(?:[.,]\d+)?)", token)
                    if token == "bl":
                        alturas.append(0.0)
                    elif m:
                        alturas.append(numero(m.group(1)))
                    else:
                        raise ValueError(
                            "Informe alturas físicas das linhas d’água no cabeçalho ou na linha abaixo."
                        )
            linhas = [
                (numero(row.iloc[1]), h, numero(row.iloc[j]))
                for _, row in df.iloc[begin:].iterrows()
                for j, h in zip(valid, alturas)
            ]
            return pd.DataFrame(linhas, columns=["x_m", "z_m", "meia_boca_m"])
        if rot[0].startswith("wl / z") and i + 2 < len(df):
            xs = [numero(v) for v in df.iloc[i + 1, 1:].dropna()]
            return pd.DataFrame(
                [
                    (x, numero(row.iloc[0]), numero(row.iloc[j + 1]))
                    for _, row in df.iloc[i + 2 :].iterrows()
                    for j, x in enumerate(xs)
                ],
                columns=["x_m", "z_m", "meia_boca_m"],
            )
    raise ValueError(
        "Cabeçalho de cotas não reconhecido. Use a aba Tabela de trabalho ou o CSV modelo."
    )


def recortar(df, topo):
    p = df.pivot(index="x_m", columns="z_m", values="meia_boca_m").sort_index(axis=1)
    if not p.columns[0] < topo <= p.columns[-1]:
        raise ValueError(
            "A altura de fechamento deve estar dentro da malha e acima do fundo."
        )
    zs = np.unique(np.r_[p.columns[p.columns < topo], topo])
    return pd.DataFrame(
        [
            (x, z, y)
            for x, row in p.iterrows()
            for z, y in zip(zs, np.interp(zs, p.columns, row))
        ],
        columns=["x_m", "z_m", "meia_boca_m"],
    )


def reconhecer_pontos(raw):
    """Usa apenas títulos dimensionais inequívocos. Rótulos locais ficam no modo manual."""
    aliases = [
        {
            "x",
            "posicao longitudinal",
            "longitudinal position",
            "distance from ap",
            "coordenada x",
        },
        {"z", "altura", "elevation", "height", "coordenada z"},
        {
            "y",
            "meia boca",
            "meia largura",
            "half breadth",
            "half breadths",
            "boca total",
            "full breadth",
            "coordenada y",
        },
    ]
    for i, row in raw.iterrows():
        nomes = []
        for item in row:
            texto = re.sub(r"[_()\[\]-]", " ", norm(item))
            texto = re.sub(r"\b(mm|cm|ft|in|m)\b", " ", texto)
            nomes.append(" ".join(texto.split()))
        idx = [[j for j, v in enumerate(nomes) if v in grupo] for grupo in aliases]
        if all(len(x) == 1 for x in idx):
            cols = [x[0] for x in idx]
            out = pontos(raw, i + 1, len(raw), cols)
            out.attrs["titulos"] = [str(row.iloc[j]) for j in cols]
            return out
    raise ValueError("Escolha as colunas de X, Z e largura.")


def coordenada(v):
    """Uma coordenada física ou um rótulo com coordenada explícita."""
    try:
        return numero(v)
    except (ValueError, TypeError):
        s = norm(v)
        if s == "bl":
            return 0.0
        num = r"([-+]?(?:\d+(?:[.,]\d+)?|[.,]\d+))"
        padroes = [
            r"(?:[xz]\s*=\s*|la[_ ])" + num,
            r"(?:^|\s)" + num + r"\s*(?:mm|cm|m|ft|in)\b",
        ]
        for p in padroes:
            m = re.search(p, s)
            if m:
                return numero(m.group(1))
        raise ValueError(
            f"'{v}' não identifica uma posição física. Indique a linha de coordenadas ou digite os valores do eixo."
        )


def celula(v, row, col, vazio=False):
    if pd.isna(v) or str(v).strip() == "":
        if vazio:
            return np.nan
    try:
        return numero(v)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"Linha {row + 1}, coluna {col + 1}: confira o valor {str(v)!r}."
        ) from exc


def pontos(raw, inicio, fim, cols):
    if len(set(cols)) != len(cols):
        raise ValueError("Escolha colunas diferentes para cada coordenada.")
    dados = []
    for i in range(inicio, fim):
        vals = raw.iloc[i, cols]
        if vals.isna().all():
            continue
        dados.append(
            [celula(v, i, j, k == 2) for k, (j, v) in enumerate(zip(cols, vals))]
        )
    return pd.DataFrame(dados, columns=COLUNAS)


def matriz(raw, inicio, fim, eixo, col_eixo, cols, coords):
    if (
        not cols
        or col_eixo in cols
        or len(cols) != len(coords)
        or len(set(coords)) != len(coords)
    ):
        raise ValueError("Cada coluna de boca deve ter uma coordenada física distinta.")
    result = []
    for i in range(inicio, fim):
        row = raw.iloc[i]
        if row[[col_eixo] + cols].isna().all():
            continue
        a = celula(row.iloc[col_eixo], i, col_eixo)
        for j, b in zip(cols, coords):
            x, z = (a, b) if eixo == "X" else (b, a)
            result.append((x, z, celula(row.iloc[j], i, j, True)))
    return pd.DataFrame(result, columns=COLUNAS)


def normalizar(
    df, unidades=("m", "m", "m"), medida="Meia-boca", vazios="Revisar células"
):
    dados = df[COLUNAS].copy().reset_index(drop=True)
    if dados.empty:
        raise ValueError("O intervalo selecionado está vazio.")
    for col, u in zip(COLUNAS, unidades):
        dados[col] = dados[col].astype(float) * UNIDADES[u]
    if not np.isfinite(dados[COLUNAS[:2]]).all().all():
        raise ValueError("Confira as coordenadas X e Z.")
    if medida == "Boca total":
        dados.meia_boca_m /= 2
    elif medida == "Y em relação à linha de centro":
        dados.meia_boca_m = dados.meia_boca_m.abs()
    if (dados.meia_boca_m < 0).any():
        raise ValueError(
            "Há larguras negativas. Para coordenadas Y medidas da linha de centro, selecione essa convenção."
        )
    dados = dados.drop_duplicates()
    if dados.duplicated(COLUNAS[:2]).any():
        raise ValueError(
            "Duas larguras diferentes para a mesma baliza e altura. Confira os bordos ou a região selecionada."
        )
    p = (
        dados.pivot(index="x_m", columns="z_m", values="meia_boca_m")
        .sort_index()
        .sort_index(axis=1)
    )
    if min(p.shape) < 2:
        raise ValueError("São necessárias ao menos duas balizas e duas alturas.")
    if vazios == "Interpolar em Z entre valores conhecidos":
        p = p.T.interpolate(method="index", limit_area="inside").T
    if vazios == "Assumir meia-boca zero":
        p = p.fillna(0.0)
    if p.isna().any().any():
        a, b = np.argwhere(p.isna().to_numpy())[0]
        raise ValueError(
            f"Falta meia-boca em X = {p.index[a]:g} m, Z = {p.columns[b]:g} m. Revise a área ou escolha o tratamento de lacunas."
        )
    if not np.isfinite(p).all().all() or p.to_numpy().max() <= 0:
        raise ValueError("A geometria precisa de larguras positivas e finitas.")
    return p.stack().rename(COLUNAS[2]).reset_index()
