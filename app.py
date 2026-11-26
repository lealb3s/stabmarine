from copy import deepcopy
from io import BytesIO

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from cenarios import PESOS, TANQUES, transferir
from entrada import EXCEL, TEXTOS, numero
from importador import painel_casco, referencia
from estabilidade import avaliar
from geometria import ANG, Casco, cruzadas
from projeto import salvar, ler
from zipfile import BadZipFile

st.set_page_config(
    page_title="AP1.5 · Estabilidade transversal", page_icon="⚓", layout="wide"
)
st.markdown(
    """<style>
.block-container{max-width:1390px;padding-top:2.3rem}
h1,h2,h3{font-family:"Barlow",system-ui,sans-serif;letter-spacing:-.03em}
[data-testid="stMetric"]{border-top:3px solid #17857e;background:#f1f6f6;border-radius:4px;padding:12px 16px}
[data-testid="stMetricValue"]{font-family:"Barlow",system-ui,sans-serif;color:#13404a}
</style>""",
    unsafe_allow_html=True,
)
ss = st.session_state


@st.cache_data
def gerar(tabela):
    casco = Casco(tabela)
    v = np.linspace(0.03, 0.97, 31) * casco.cap
    return v, cruzadas(casco, v)


@st.cache_data
def calcular(tabela, vs, kn, cond, rho, limites, intervalo):
    return avaliar(Casco(tabela), vs, kn, cond, rho, limites, intervalo)


if "casos" not in ss:
    ss.tabela = None
    ss.casco_nome = ""
    ss.casos = {}
    ss.versao = 0
if "restaurar" in ss:
    ss.casco_nome, ss.rho, ss.tabela, ss.vs, ss.casos, ss.kn = ss.pop("restaurar")
    ss.versao += 1


def csv(df):
    return df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")


def baixar(texto, df, nome):
    st.download_button(texto, csv(df), nome, "text/csv")


def aplicar(nome, cond):
    calcular(ss.tabela, ss.vs, ss.kn, cond, ss.rho, (-100.0, 100.0), (0.0, 40.0))
    ss.casos[nome] = deepcopy(cond)
    ss.versao += 1
    ss.aviso = "Condição atualizada."
    st.rerun()


def grafico(df, y, grupo, ylabel, limites=None):
    data = df.copy()
    if limites:
        data = data[data["Banda (°)"].between(*limites)]
    base = (
        alt.Chart(data)
        .mark_line(strokeWidth=2.5)
        .encode(
            x=alt.X("Banda (°):Q", title="Banda (°) · boreste positivo"),
            y=alt.Y(f"{y}:Q", title=ylabel, scale=alt.Scale(zero=False)),
            color=alt.Color(
                f"{grupo}:N",
                title=None,
                scale=alt.Scale(
                    range=[
                        "#077d75",
                        "#bb5a29",
                        "#344f98",
                        "#89558c",
                        "#a87e15",
                        "#253e47",
                        "#74958c",
                    ]
                ),
                legend=alt.Legend(orient="bottom", columns=3),
            ),
            strokeDash=alt.StrokeDash(f"{grupo}:N", legend=None),
            tooltip=[
                grupo,
                alt.Tooltip("Banda (°):Q", format=".1f"),
                alt.Tooltip(f"{y}:Q", format=".5f"),
            ],
        )
    )
    zero = (
        alt.Chart(pd.DataFrame({"zero": [0]}))
        .mark_rule(color="#9aaeb0")
        .encode(y="zero:Q")
    )
    st.altair_chart(
        (zero + base).properties(height=345).interactive(bind_y=False), width="stretch"
    )


def livro(tabelas):
    mem = BytesIO()
    with pd.ExcelWriter(mem, engine="openpyxl") as xl:
        for nome, df in tabelas.items():
            df.to_excel(xl, sheet_name=nome, index=False)
    return mem.getvalue()


def resultado(nome):
    return calcular(ss.tabela, ss.vs, ss.kn, ss.casos[nome], ss.rho, limites, intervalo)


st.sidebar.title("Estabilidade naval")
pag = st.sidebar.radio(
    "Área de trabalho",
    ["Casco e curvas KN", "Cargas e tanques", "Comparação GZ", "Validação"],
    label_visibility="collapsed",
    key="area_trabalho",
)
st.sidebar.divider()
st.sidebar.caption("EMBARCAÇÃO ATIVA")
st.sidebar.write(ss.casco_nome or "Nenhum casco cadastrado")
st.sidebar.number_input(
    "Densidade da água (t/m³)",
    min_value=0.1,
    max_value=2.0,
    format="%.4f",
    step=0.001,
    value=None,
    placeholder="Informe a densidade",
    key="rho",
)
with st.sidebar.expander("Limites de análise"):
    definidos = st.checkbox("Aplicar limites de alagamento")
    if definidos:
        bb = st.number_input("Alagamento a bombordo (módulo, °)", 0.1, 100.0, 80.0)
        be = st.number_input("Alagamento a boreste (°, positivo)", 0.1, 100.0, 80.0)
    else:
        bb = be = 100.0
    intervalo = st.slider("Integração da área assinada (°)", -100, 100, (0, 40))
    st.caption(
        "Use limites válidos para todas as condições selecionadas. Área em m·rad. Um intervalo que ultrapassa o alagamento fica sem resultado."
    )
with st.sidebar.expander("Salvar ou abrir projeto"):
    if ss.tabela is not None and ss.rho is not None:
        st.download_button(
            "Salvar sessão em JSON",
            salvar(ss.casco_nome, ss.rho, ss.tabela, ss.vs, ss.casos),
            "projeto_AP15.json",
            "application/json",
        )
    sessao = st.file_uploader("Abrir sessão salva", type=["json"])
    if sessao and st.button("Restaurar sessão"):
        try:
            dados = ler(sessao.getvalue())
            with st.spinner("Recalculando KN do projeto…"):
                ss.restaurar = (*dados, cruzadas(Casco(dados[2]), dados[3]))
            st.rerun()
        except (ValueError, TypeError, KeyError, IndexError, AttributeError) as e:
            st.error(f"Projeto inválido. {e}")
limites = (-bb, be)
if "aviso" in ss:
    st.success(ss.pop("aviso"))

def abrir_pagina(pagina):
    ss.area_trabalho = pagina


if pag in ("Comparação GZ", "Cargas e tanques"):
    if ss.tabela is None:
        st.info("Informe a geometria da sua embarcação para iniciar o estudo.")
        st.button("Cadastrar casco", on_click=abrir_pagina, args=("Casco e curvas KN",))
        st.stop()
    if ss.rho is None:
        st.info("Informe a densidade da água na barra lateral para calcular o carregamento.")
        st.stop()

condicoes_com_pesos = [n for n, c in ss.casos.items() if c["pesos"] or c["tanques"]]

if pag == "Comparação GZ":
    st.title("Curvas de estabilidade")

    if not condicoes_com_pesos:
        st.info("Cadastre a massa da embarcação leve e os demais pesos para calcular a curva GZ.")
        st.button("Cadastrar carregamento", on_click=abrir_pagina, args=("Cargas e tanques",))
        st.stop()
    st.caption(f"{ss.casco_nome}  /  Estabilidade transversal intacta")
    nomes = condicoes_com_pesos
    escolhas = st.multiselect(
        "Condições no gráfico",
        nomes,
        default=nomes,
        key=f"cmp_{len(nomes)}_{ss.casco_nome}",
    )
    fixo = st.checkbox("Sobrepor o líquido imobilizado para a condição em destaque")
    if not escolhas:
        st.info("Selecione uma condição para comparar.")
        st.stop()
    foco = st.selectbox("Condição em destaque", escolhas)
    res = {}
    for nome in escolhas:
        try:
            res[nome] = resultado(nome)
        except ValueError as e:
            st.warning(f"{nome} · {e}")
    if not res:
        st.stop()
    if foco not in res:
        foco = next(iter(res))
    m, g, roots, sinais = res[foco]
    for col, k, un in zip(
        st.columns(4),
        ["Δ (t)", "GM corr. (m)", "Equilíbrio (°)", "GZ máx. (m)"],
        ["t", "m", "°", "m"],
    ):
        val = m[k]
        col.metric(
            k.split(" (")[0],
            f"{val:.3f} {un}".replace(".", ",")
            if np.isfinite(val)
            else "Indeterminado",
        )
    curvas = pd.concat(
        [r[1].assign(Condição=n) for n, r in res.items()], ignore_index=True
    )
    plot = curvas
    if fixo:
        plot = pd.concat(
            [
                plot,
                g.assign(
                    Condição="Líquido fixo · " + foco,
                    **{"GZ (m)": g["GZ líquido fixo (m)"]},
                ),
            ]
        )
    grafico(plot, "GZ (m)", "Condição", "Braço de endireitamento GZ (m)")
    st.caption(
        f"Passo de 2°. Indicadores calculados entre {limites[0]:g}° e +{limites[1]:g}°. "
        + (
            "A curva fora desses limites representa apenas a geometria intacta."
            if definidos
            else "Ângulos de alagamento não informados."
        )
    )
    resumo = pd.DataFrame([dict(Condição=n, **r[0]) for n, r in res.items()])
    st.subheader("Comparação das condições")
    st.dataframe(resumo, hide_index=True, width="stretch")
    st.caption(
        f"Área integrada de {intervalo[0]}° a {intervalo[1]}°. Equilíbrio apresentado = raiz estável mais próxima de 0° no intervalo analisado."
    )

    def lista(x):
        return " | ".join(x) or "Nenhum no intervalo"

    with st.expander("Zeros, sinais e dados da curva", expanded=False):
        st.write(foco)
        delta = m["Δ (t)"]
        grid = ss.vs * ss.rho
        if np.isclose(grid, delta, rtol=1e-12).any():
            st.write(f"KN avaliado no deslocamento tabulado de {delta:.3f} t.")
        else:
            i = np.searchsorted(grid, delta)
            st.write(f"KN interpolado entre {grid[i - 1]:.3f} e {grid[i]:.3f} t.")
        st.write("Zeros de GZ (°) — " + lista([f"{v:.2f}" for v in roots]))
        st.write("GZ positivo (°) — " + lista(sinais["+"]))
        st.write("GZ negativo (°) — " + lista(sinais["−"]))
        st.caption(
            "Em ambos os bordos, a estabilidade local de uma raiz depende da inclinação positiva de GZ. O sinal do braço indica o sentido do momento."
        )
        st.dataframe(g, hide_index=True, width="stretch")
    faixa = pd.DataFrame(
        [
            {
                "Condição": n,
                "Zeros (°)": lista([f"{v:.4f}" for v in r[2]]),
                "GZ positivo (°)": lista(r[3]["+"]),
                "GZ negativo (°)": lista(r[3]["−"]),
            }
            for n, r in res.items()
        ]
    )
    tabelas = {
        "Resumo": resumo,
        "Curvas": curvas,
        "Intervalos": faixa,
        "Cotas": ss.tabela,
        "Pesos": pd.concat(
            [pd.DataFrame(ss.casos[n]["pesos"]).assign(Condição=n) for n in res]
        ),
        "Tanques": pd.concat(
            [pd.DataFrame(ss.casos[n]["tanques"]).assign(Condição=n) for n in res]
        ),
        "Parâmetros": pd.DataFrame(
            [
                {
                    "Casco": ss.casco_nome,
                    "Densidade (t/m³)": ss.rho,
                    "Área de (°)": intervalo[0],
                    "Área até (°)": intervalo[1],
                    "Limite BB (°)": -bb,
                    "Limite BE (°)": be,
                    "Alagamento informado": definidos,
                }
            ]
        ),
    }
    c1, c2 = st.columns(2)
    with c1:
        baixar("Baixar curvas em CSV", curvas, "curvas_gz.csv")
    c2.download_button(
        "Baixar comparação em Excel", livro(tabelas), "comparacao_AP15.xlsx"
    )

elif pag == "Cargas e tanques":
    st.title("Cargas e tanques")
    st.caption(
        "X parte da origem das balizas, Y é positivo a boreste e Z parte da linha de base. Massas em toneladas e dimensões em metros."
    )
    nome = st.selectbox("Condição para editar", list(ss.casos), key="editar")
    cond = ss.casos[nome]
    with st.expander("Criar uma cópia para experimentar"):
        novo = st.text_input("Nome da nova condição", max_chars=60)
        if st.button("Duplicar condição"):
            novo = novo.strip()
            if novo and novo not in ss.casos:
                ss.casos[novo] = deepcopy(cond)
                ss.aviso = "Cópia criada. Selecione a nova condição para editá-la."
                st.rerun()
            st.error("Escolha um nome novo e não vazio.")

    def editor(chave, colunas):
        df = pd.DataFrame(cond[chave], columns=colunas)
        df[colunas[0]] = df[colunas[0]].astype("string")
        for col in colunas[1:]:
            df[col] = df[col].astype(float)
        return (
            st.data_editor(
                df,
                num_rows="dynamic",
                hide_index=True,
                width="stretch",
                key=f"{ss.versao}_{nome}_{chave}",
                column_config={
                    c: st.column_config.NumberColumn(format="%.4f") for c in colunas[1:]
                },
            )
            .dropna(how="all")
            .to_dict("records")
        )

    with st.expander("Importar pesos e tanques do Excel"):
        st.caption("Preencha as abas Pesos e Tanques do modelo. Para uma condição sem tanques, deixe apenas o cabeçalho na aba Tanques. A importação substitui as duas tabelas da condição selecionada.")
        modelo = {"Pesos": pd.DataFrame(columns=PESOS), "Tanques": pd.DataFrame(columns=TANQUES)}
        st.download_button("Baixar modelo vazio", livro(modelo), "carregamento.xlsx")
        planilha = st.file_uploader("Planilha de carregamento", type=["xlsx"], key="inventario_" + nome)
        if planilha and st.button("Importar e recalcular"):
            try:
                with pd.ExcelFile(BytesIO(planilha.getvalue()), engine="openpyxl") as arquivo:
                    inventario = {}
                    for aba, colunas in (("Pesos", PESOS), ("Tanques", TANQUES)):
                        dados = arquivo.parse(aba)
                        if not set(colunas).issubset(dados.columns):
                            raise ValueError(f"Confira os cabeçalhos da aba {aba} no modelo.")
                        dados = dados[colunas].dropna(how="all").copy()
                        dados[colunas[1:]] = dados[colunas[1:]].map(numero)
                        inventario[aba.lower()] = dados.to_dict("records")
                aplicar(nome, inventario)
            except (ValueError, TypeError, KeyError, OSError, BadZipFile) as exc:
                st.error(f"Confira a planilha de carregamento. {exc}")

    with st.form("inventario"):
        st.subheader("Pesos sólidos")
        st.caption(
            "Na primeira linha, digite a massa da embarcação leve e seu centro de gravidade (X = LCG, Y = TCG e Z = KG). Acrescente uma linha por carga. Os líquidos entram na tabela de tanques."
        )
        p = editor("pesos", PESOS)
        st.subheader("Tanques retangulares")
        st.caption(
            "X e Y localizam o centro em planta. Fundo é a cota inferior. A massa do líquido entra automaticamente no balanço."
        )
        t = editor("tanques", TANQUES)
        if st.form_submit_button("Aplicar e recalcular", type="primary"):
            try:
                aplicar(nome, {"pesos": p, "tanques": t})
            except ValueError as e:
                st.error(str(e))
    with st.expander("Transferir líquido entre tanques"):
        opts = [r["Tanque"] for r in cond["tanques"]]
        if len(opts) >= 2:
            a, b, c = st.columns(3)
            origem = a.selectbox("Origem", opts, key="orig_" + nome)
            destino = b.selectbox("Destino", opts, index=1, key="dest_" + nome)
            vol = c.number_input(
                "Volume a transferir (m³)", min_value=0.001, value=1.0, format="%.3f"
            )
            if st.button("Executar transferência"):
                try:
                    aplicar(nome, transferir(cond, origem, destino, vol))
                except ValueError as e:
                    st.error(str(e))
        else:
            st.info("Cadastre pelo menos dois tanques.")
    if not cond["pesos"] and not cond["tanques"]:
        st.stop()
    try:
        m = resultado(nome)[0]
        st.write(
            f"Deslocamento de {m['Δ (t)']:.3f} t · KG de {m['KG (m)']:.4f} m · TCG de {m['TCG (m)']:.4f} m · FSC de {m['FSC (m)']:.4f} m."
        )
    except ValueError as e:
        st.warning(str(e))

elif pag == "Casco e curvas KN":
    st.title("Casco e curvas cruzadas")
    novo = painel_casco()
    if novo is not None:
        nome, tabela = novo
        try:
            with st.spinner("Calculando as curvas KN do casco…"):
                vs, kn = gerar(tabela)
            ss.tabela, ss.vs, ss.kn = tabela, vs, kn
            ss.casco_nome = nome
            ss.casos = {"1 · Inicial": {"pesos": [], "tanques": []}}
            ss.versao += 1
            ss.aviso = "Casco cadastrado. Informe a densidade da água e cadastre o carregamento inicial."
            st.rerun()
        except (ValueError, TypeError, ArithmeticError) as exc:
            st.error(f"Não foi possível aplicar a geometria. {exc}")
    if ss.tabela is None:
        st.stop()
    casco = Casco(ss.tabela)
    st.write(
        f"{ss.casco_nome} · {len(casco.x)} balizas · {len(casco.z)} linhas d’água · volume fechado de {casco.cap:.3f} m³."
    )
    with st.expander("Tabela de cotas do casco ativo"):
        st.dataframe(ss.tabela, hide_index=True, width="stretch")
        baixar("Baixar cotas em CSV", ss.tabela, "cotas.csv")
        st.download_button(
            "Baixar modelo em Excel", livro({"Cotas": ss.tabela}), "modelo_casco.xlsx"
        )
    st.button("Cadastrar carregamento", on_click=abrir_pagina, args=("Cargas e tanques",))
    if ss.rho is None:
        st.info("Informe a densidade da água na barra lateral para ver KN em função do deslocamento.")
        st.stop()
    deltas = ss.vs * ss.rho
    st.write(
        f"Interpolação linear entre {deltas[0]:.3f} e {deltas[-1]:.3f} t para a densidade atual. Fora da faixa, a condição é bloqueada."
    )
    # Convenção naval: KN versus deslocamento para cada ângulo de banda.
    knl = (
        pd.DataFrame(ss.kn, index=deltas, columns=ANG)
        .rename_axis("Δ (t)")
        .reset_index()
        .melt("Δ (t)", var_name="Banda (°)", value_name="KN (m)")
    )
    sel = st.multiselect(
        "Ângulos das curvas cruzadas (°)",
        list(ANG),
        default=[10.0, 30.0, 50.0, 70.0, 90.0],
    )
    sub = knl[knl["Banda (°)"].isin(sel)]
    st.altair_chart(
        alt.Chart(sub)
        .mark_line()
        .encode(
            x="Δ (t):Q",
            y="KN (m):Q",
            color="Banda (°):N",
            tooltip=["Δ (t):Q", "Banda (°):Q", "KN (m):Q"],
        )
        .properties(height=320),
        width="stretch",
    )
    baixar("Baixar tabela KN completa", knl, "curvas_kn.csv")
    with st.expander("Seções e propriedades hidrostáticas"):
        est = st.select_slider(
            "Baliza em X (m)", options=list(casco.x), value=casco.x[len(casco.x) // 2]
        )
        w = casco.b[np.where(casco.x == est)[0][0]]
        sec = pd.DataFrame(
            {
                "Y (m)": np.r_[w, -w[::-1], w[:1]],
                "Z (m)": np.r_[casco.z, casco.z[::-1], casco.z[:1]],
            }
        )
        sec["ordem"] = np.arange(len(sec))
        st.altair_chart(
            alt.Chart(sec)
            .mark_line()
            .encode(x="Y (m):Q", y="Z (m):Q", order="ordem:Q"),
            width="stretch",
        )
        hidro = pd.DataFrame(
            [{"Δ (t)": v * ss.rho, "∇ (m³)": v, **casco.hidro(v)} for v in ss.vs]
        )
        st.dataframe(hidro, hide_index=True, width="stretch")
        baixar("Baixar hidrostáticas", hidro, "hidrostaticas.csv")

else:
    st.title("Validação dos cálculos")
    st.write(
        "Os controles abaixo verificam o método de cálculo em prismas com solução analítica conhecida. Para validar uma condição da sua embarcação, importe uma curva de referência abaixo."
    )
    from verificacao import validar

    controles = {
        "balanco": "Movimento de pesos e superfície livre",
        "analitica": "Braços em cinco ângulos",
        "tupper": "Comparação com a fórmula de Tupper",
    }
    tabelas_validacao = st.cache_data(validar)()
    for (n, title), df in zip(controles.items(), tabelas_validacao):
        with st.expander(title, expanded=n == "balanco"):
            if n != "balanco":
                long = df.melt(
                    id_vars="Banda (°)",
                    value_vars=["Referência (m)", "App (m)"],
                    var_name="Origem",
                    value_name="GZ (m)",
                )
                grafico(long, "GZ (m)", "Origem", "GZ (m)")
            st.dataframe(df, hide_index=True, width="stretch")
    st.subheader("Comparar com uma curva externa")
    if not condicoes_com_pesos or ss.rho is None:
        st.info("Cadastre o casco, a densidade da água e o carregamento para comparar sua curva GZ.")
        st.stop()
    st.caption(
        "Selecione as colunas de banda e de GZ, com pelo menos dois ângulos distintos. Iguale casco, carregamento, densidade, convenção de sinal, trim e tratamento dos líquidos antes da comparação."
    )
    n = st.selectbox("Condição de referência", condicoes_com_pesos)
    arq = st.file_uploader("Planilha com a curva de referência", type=EXCEL + TEXTOS)
    if arq:
        try:
            ref = referencia(arq)
            if (
                len(ref) < 2
                or not np.isfinite(ref).all().all()
                or ref.banda_deg.duplicated().any()
                or not ref.banda_deg.between(*limites).all()
            ):
                raise ValueError(
                    "Confira o intervalo válido, os ângulos repetidos e os valores vazios."
                )
            g = resultado(n)[1]
            from verificacao import comparacao

            tab = comparacao(
                ref.banda_deg.to_numpy(),
                ref.gz_m.to_numpy(),
                np.interp(ref.banda_deg, ANG, g["GZ (m)"]),
            )
            long = tab.melt(
                id_vars="Banda (°)",
                value_vars=["Referência (m)", "App (m)"],
                var_name="Origem",
                value_name="GZ (m)",
            )
            grafico(long, "GZ (m)", "Origem", "GZ (m)")
            st.dataframe(tab, hide_index=True)
            baixar("Baixar diferenças", tab, "validacao_externa.csv")
        except (ValueError, KeyError, IndexError, OSError, BadZipFile) as e:
            st.error(f"Não foi possível comparar. {e}")
