"""Interface de importação com prévia do arquivo e conversão para o modelo do AP1.5."""

from hashlib import sha256
from pathlib import Path
import re
import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from entrada import (
    EXCEL,
    TEXTOS,
    UNIDADES,
    abas,
    bruto,
    automatico,
    coordenada,
    pontos,
    matriz,
    normalizar,
    norm,
    recortar,
    reconhecer_pontos,
)
from cad import objetos_rhino, triangulos, eixos, offsets
from geometria import Casco


@st.cache_data(show_spinner=False, max_entries=12)
def abrir(data, nome, aba):
    return bruto(data, nome, aba)


@st.cache_data(show_spinner=False, max_entries=8)
def folhas(data, nome):
    return abas(data, nome)


@st.cache_data(show_spinner=False, max_entries=3)
def malha(data, nome, ids):
    return triangulos(data, nome, ids)


@st.cache_data(show_spinner=False, max_entries=3)
def secoes_cad(t, nx, nz, centro, modo):
    return offsets(t, nx, nz, centro, modo)


def ler_aba(arq, chave):
    data = arq.getvalue()
    nomes = folhas(data, arq.name)
    aba = None
    if nomes:
        candidato = next(
            (n for n in nomes if norm(n) == "tabela de trabalho"), nomes[0]
        )
        aba = st.selectbox(
            "Aba da planilha", nomes, index=nomes.index(candidato), key=chave + "aba"
        )
    return abrir(data, arq.name, aba), chave + str(aba)


def previa_bruta(raw):
    if raw.empty:
        raise ValueError("A aba selecionada está vazia.")
    d = raw.fillna("").astype(str)
    d.index = pd.RangeIndex(1, len(d) + 1, name="Linha")
    d.columns = [letra(i) for i in range(d.shape[1])]
    with st.expander("Ver células e números das linhas"):
        st.dataframe(d, width="stretch", height=220)


def letra(i):
    out = ""
    while i >= 0:
        i, r = divmod(i, 26)
        out = chr(65 + r) + out
        i -= 1
    return out


def rotulos(row):
    return [
        letra(j) + (" · " + str(v)[:55] if pd.notna(v) else "")
        for j, v in enumerate(row)
    ]


def indice_sugerido(row, aliases, padrao):
    for j, v in enumerate(row):
        txt = re.sub(r"[^a-z0-9 ]", " ", norm(v)).strip()
        if any(txt == k or txt.startswith(k + " ") for k in aliases):
            return j
    return min(padrao, len(row) - 1)


def header_sugerido(raw):
    for i, row in raw.iterrows():
        if any(
            re.match(
                r"^(?:x|baliza|estacao|station|wl|banda|angle|heel|angulo)(?:\b|[_ (])",
                norm(v),
            )
            for v in row
        ):
            return i + 1
    return 1


def linhas(raw, k):
    n = len(raw)
    a, b, c = st.columns(3)
    header = a.number_input(
        "Linha dos rótulos", 1, n, min(header_sugerido(raw), n), key=k + "head"
    )
    inicio = b.number_input(
        "Primeira linha de dados",
        1,
        n,
        min(header + 1, n),
        key=k + "start" + str(header),
    )
    fim = c.number_input(
        "Última linha de dados", inicio, n, n, key=k + "end" + str(inicio)
    )
    return raw.iloc[header - 1], inicio - 1, fim


def unidade(chave, rotulo, texto=""):
    token = re.search(r"(?:^|[^a-z])(mm|cm|ft|in|m)(?:$|[^a-z])", norm(texto))
    op = list(UNIDADES)
    return st.selectbox(
        rotulo, op, index=op.index(token.group(1)) if token else 0, key=chave
    )


def manual(raw, k):
    modo = st.radio(
        "Organização dos dados",
        ["Pontos em três colunas", "Balizas nas linhas", "Alturas nas linhas"],
        horizontal=True,
        key=k + "tipo",
    )
    row, a, b = linhas(raw, k)
    labels = rotulos(row)
    ix = indice_sugerido(row, ["x", "lcg", "longitudinal", "estacao", "station"], 0)
    iz = indice_sugerido(row, ["z", "altura", "height", "elevation"], 1)
    iy = indice_sugerido(
        row, ["meia boca", "y", "half breadth", "boca", "largura", "breadth"], 2
    )
    op = list(range(len(labels)))
    if modo.startswith("Pontos"):
        if len(op) < 3:
            raise ValueError("Selecione uma aba com pelo menos três colunas.")
        cs = st.columns(3)
        idx = [
            c.selectbox(
                s, op, index=j, format_func=labels.__getitem__, key=k + modo + s
            )
            for c, s, j in zip(
                cs, ["Posição X", "Altura Z", "Largura ou Y"], [ix, iz, iy]
            )
        ]
        return pontos(raw, a, b, idx), [row.iloc[j] for j in idx]
    eixo = "X" if modo == "Balizas nas linhas" else "Z"
    outro = "Z" if eixo == "X" else "X"
    i = st.selectbox(
        "Coluna com posições " + eixo,
        op,
        index=ix if eixo == "X" else iz,
        format_func=labels.__getitem__,
        key=k + eixo + "col",
    )
    possiveis = [j for j in op if j != i]
    selecionadas = [
        j
        for j in possiveis
        if pd.to_numeric(
            raw.iloc[a:b, j].astype(str).str.replace(",", ".", regex=False),
            errors="coerce",
        )
        .notna()
        .any()
        and not re.match(r"^(baliza|estacao|station|item|id)$", norm(row.iloc[j]))
    ]
    cols = st.multiselect(
        "Colunas com larguras",
        possiveis,
        default=selecionadas,
        format_func=labels.__getitem__,
        key=k + eixo + str(i),
    )
    if len(cols) < 2:
        raise ValueError("Escolha pelo menos duas colunas de larguras.")
    fonte = st.radio(
        "Posições " + outro + " correspondentes às colunas",
        ["Ler de uma linha", "Digitar valores"],
        horizontal=True,
        key=k + eixo + "fonte",
    )
    if fonte == "Ler de uma linha":
        pos = st.number_input(
            "Linha com as posições físicas " + outro,
            1,
            len(raw),
            int(row.name) + 1,
            key=k + eixo + "pos",
        )
        coords = [coordenada(raw.iloc[pos - 1, j]) for j in cols]
    else:
        txt = st.text_input(
            "Posições em ordem, separadas por ponto e vírgula",
            key=k + eixo + "valores",
            placeholder="0; 0,25; 0,50",
        )
        if not txt.strip():
            raise ValueError(
                "Informe as posições correspondentes às colunas selecionadas."
            )
        coords = [coordenada(s) for s in txt.split(";")]
    return matriz(raw, a, b, eixo, i, cols, coords), [
        row.iloc[i] if eixo == "X" else "",
        row.iloc[i] if eixo == "Z" else "",
        "",
    ]


def geometria_planilha(arq, k):
    df, k = ler_aba(arq, k)
    previa_bruta(df)
    try:
        auto = automatico(df)
    except (ValueError, TypeError, KeyError, IndexError):
        try:
            auto = reconhecer_pontos(df)
        except (ValueError, TypeError, KeyError, IndexError):
            auto = None
    if auto is None:
        st.caption(
            "Escolha a disposição e associe as colunas. Uma aba com calado, deslocamento e KM precisa ser acompanhada das cotas do casco para gerar as curvas KN."
        )
    guiado = st.toggle(
        "Configurar leitura manualmente",
        value=auto is None,
        disabled=auto is None,
        key=k + "manual",
    )
    if guiado or auto is None:
        tab, labels = manual(df, k)
    else:
        tab, labels = auto, auto.attrs.get("titulos", ["m"] * 3)
        st.caption(
            "Formato de cotas reconhecido. Confira as unidades e as dimensões abaixo."
        )
    c1, c2, c3 = st.columns(3)
    with c1:
        ux = unidade(k + "ux" + str(labels[0]), "Unidade de X", labels[0])
    with c2:
        uz = unidade(k + "uz" + str(labels[1]), "Unidade de Z", labels[1])
    with c3:
        uy = unidade(k + "uy" + str(labels[2]), "Unidade da largura", labels[2])
    rotulo = norm(labels[2])
    medida_idx = (
        1
        if "total" in rotulo or "full breadth" in rotulo
        else (2 if re.search(r"\by\b", rotulo.replace("_", " ")) else 0)
    )
    medida = st.selectbox(
        "Valores transversais da planilha",
        ["Meia-boca", "Boca total", "Y em relação à linha de centro"],
        index=medida_idx,
        key=k + "medida" + str(labels[2]),
    )
    lacunas = st.selectbox(
        "Tratamento das cotas ausentes",
        [
            "Revisar células",
            "Interpolar em Z entre valores conhecidos",
            "Assumir meia-boca zero",
        ],
        key=k + "vazios",
    )
    return normalizar(tab, (ux, uz, uy), medida, lacunas)


def geometria_cad(arq, k):
    data = arq.getvalue()
    ids = ()
    unidades = ["m", "cm", "mm", "ft", "in"]
    unidade_inicial = "m"
    if arq.name.lower().endswith(".3dm"):
        objetos, un = objetos_rhino(data)
        if not objetos:
            raise ValueError(
                "O 3DM precisa conter a malha ou as faces do casco. No Rhino use _Mesh e exporte a seleção."
            )
        op = list(objetos)
        ids = tuple(
            st.multiselect(
                "Objetos que formam o casco",
                op,
                default=op if len(op) == 1 else [],
                format_func=objetos.__getitem__,
                key=k + "obj",
            )
        )
        if not ids:
            st.info("Selecione os objetos do casco na lista acima.")
            return
        mapa = {
            "Meters": "m",
            "Centimeters": "cm",
            "Millimeters": "mm",
            "Feet": "ft",
            "Inches": "in",
        }
        st.caption("Unidade registrada no Rhino: " + un)
        unidade_inicial = mapa.get(un, "m")
    t = malha(data, arq.name, ids)
    cs = st.columns(3)
    u = cs[0].selectbox(
        "Unidade do modelo",
        unidades,
        index=unidades.index(unidade_inicial),
        key=k + "uni",
    )
    long = cs[1].selectbox("Eixo longitudinal", ["X", "Y", "Z"], key=k + "x")
    vert = cs[2].selectbox("Eixo vertical", ["X", "Y", "Z"], index=2, key=k + "z")
    op = st.columns(2)
    rx = op[0].checkbox("Inverter sentido longitudinal", key=k + "rx")
    rz = op[1].checkbox("Inverter sentido vertical", key=k + "rz")
    t = eixos(t, "XYZ".index(long), "XYZ".index(vert), UNIDADES[u], rx, rz)
    modo = st.selectbox(
        "Geometria do arquivo",
        ["Casco completo", "Meio casco em Y positivo", "Meio casco em Y negativo"],
        key=k + "modo",
    )
    baixo, alto = t[:, :, 1].min(), t[:, :, 1].max()
    plano = (
        (baixo + alto) / 2
        if modo == "Casco completo"
        else (baixo if modo.endswith("positivo") else alto)
    )
    centro = st.number_input(
        "Plano de centro no eixo transversal original (m)",
        value=float(plano),
        format="%.6f",
        key=k + str(plano) + "centro",
    )
    st.caption(
        "X = 0 na primeira extremidade do sentido escolhido e Z = 0 no ponto mais baixo. A seção usa um monocasco simétrico. Exporte somente a superfície externa, sem casaria, hélice ou apêndices."
    )
    c1, c2 = st.columns(2)
    nx = c1.number_input("Número de balizas", 3, 101, 21, key=k + "nx")
    nz = c2.number_input("Número de alturas", 3, 81, 17, key=k + "nz")
    return secoes_cad(t, nx, nz, centro, modo)


def painel_casco():
    st.subheader("Importar meu casco")
    st.caption(
        "Carregue o arquivo 3D ou uma tabela com as dimensões das seções. A prévia permite conferir o casco antes de aplicá-lo."
    )
    arq = st.file_uploader(
        "Arquivo do casco ou planilha de cotas",
        type=["3dm", "stl", "obj"] + EXCEL + TEXTOS,
        key="importar_casco",
    )
    if not arq:
        return
    k = sha256(arq.getvalue()).hexdigest()[:16] + arq.name
    cad = Path(arq.name).suffix.lower() in (".3dm", ".obj", ".stl")
    try:
        tab = geometria_cad(arq, k) if cad else geometria_planilha(arq, k)
        if tab is None:
            return
        c = Casco(tab)
        topo = st.number_input(
            "Cota de fechamento estanque (m)",
            min_value=float(c.z[0]),
            max_value=float(c.z[-1]),
            value=float(c.z[-1]),
            format="%.5f",
            key=k + str((c.z[0], c.z[-1])) + "teto",
        )
        tab = recortar(tab, topo)
        c = Casco(tab)
        if c.cap <= 0:
            raise ValueError(
                "O volume das seções é nulo. Confira a cota de fechamento."
            )
    except Exception as exc:
        st.warning(str(exc) or "Confira a integridade do arquivo e as unidades.")
        return
    st.write(
        f"Comprimento **{np.ptp(c.x):.3f} m** · Boca **{2 * c.b.max():.3f} m** · Altura **{np.ptp(c.z):.3f} m** · Volume fechado **{c.cap:.3f} m³**"
    )
    with st.expander("Conferir as seções importadas", expanded=True):
        ix = st.select_slider(
            "Posição longitudinal da seção (m)",
            options=c.x.tolist(),
            value=float(c.x[len(c.x) // 2]),
            key=k + "bal" + str(tuple(c.x)),
        )
        y = c.b[np.where(c.x == ix)[0][0]]
        sec = pd.DataFrame(
            {"Y (m)": np.r_[y, -y[::-1], y[0]], "Z (m)": np.r_[c.z, c.z[::-1], c.z[0]]}
        )
        sec["ordem"] = np.arange(len(sec))
        st.altair_chart(
            alt.Chart(sec)
            .mark_line(color="#087d73", point=True)
            .encode(x="Y (m):Q", y="Z (m):Q", order="ordem:Q")
            .properties(height=200),
            width="stretch",
        )
    st.caption(
        "Aplicar abre um estudo com massa inicial de exemplo. Para guardar o estudo atual, use Salvar sessão em JSON."
    )
    if st.button("Aplicar novo casco", type="primary"):
        return arq.name, tab


def referencia(arq):
    k = "ref" + sha256(arq.getvalue()).hexdigest()[:16]
    df, k = ler_aba(arq, k)
    previa_bruta(df)
    row, a, b = linhas(df, k)
    labels = rotulos(row)
    op = list(range(len(labels)))
    if len(op) < 2:
        raise ValueError("Selecione uma aba com colunas de banda e GZ.")
    c1, c2 = st.columns(2)
    ang = c1.selectbox(
        "Coluna de banda (°)",
        op,
        index=indice_sugerido(row, ["banda", "heel", "angle", "angulo"], 0),
        format_func=labels.__getitem__,
        key=k + "ang",
    )
    gz = c2.selectbox(
        "Coluna de GZ",
        op,
        index=indice_sugerido(row, ["gz", "braco", "righting arm"], 1),
        format_func=labels.__getitem__,
        key=k + "gz",
    )
    if ang == gz:
        raise ValueError("Escolha duas colunas diferentes.")
    from entrada import numero

    tab = df.iloc[a:b, [ang, gz]].dropna(how="all").map(numero)
    tab.columns = ["banda_deg", "gz_m"]
    tab.gz_m *= UNIDADES[unidade(k + "uni", "Unidade de GZ", row.iloc[gz])]
    return tab.sort_values("banda_deg")
