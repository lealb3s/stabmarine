"""Reproduz os seis estudos e os ensaios complementares a partir das cotas Damen."""

from copy import deepcopy
from pathlib import Path
import numpy as np
import pandas as pd
from cenarios import exemplos, NOMES
from estabilidade import avaliar
from geometria import Casco

DADOS = Path(__file__).parent / "dados"


def estudos():
    casco = Casco(pd.read_csv(DADOS / "damen.csv"))
    with np.load(DADOS / "cruzadas_damen.npz") as arq:
        vs, k = arq["volumes"], arq["kn"]
    casos = exemplos()
    curvas = []
    indicadores = []
    faixas = []

    def registrar(nome, cond):
        m, g, zeros, sg = avaliar(casco, vs, k, cond)
        indicadores.append(dict(Condição=nome, **m))
        curvas.append(g.assign(Condição=nome))
        faixas.append(
            {
                "Condição": nome,
                "Zeros (°)": ", ".join(f"{z:.4f}" for z in zeros),
                "GZ positivo (°)": " | ".join(sg["+"]),
                "GZ negativo (°)": " | ".join(sg["−"]),
            }
        )

    for nome, cond in casos.items():
        registrar(nome, cond)
    for y in [0.6, 1.2]:
        c = deepcopy(casos[NOMES[0]])
        c["pesos"][-1]["Y_m"] = y
        registrar(f"Transversal {y:.1f} m", c)
    for dm in [-2.0, 2.0]:
        c = deepcopy(casos[NOMES[0]])
        c["pesos"][-1]["Massa_t"] += dm
        registrar(f"Variação {dm:+.0f} t", c)
    for arquivo, df in [
        ("indicadores", pd.DataFrame(indicadores)),
        ("curvas", pd.concat(curvas, ignore_index=True)),
        ("intervalos", pd.DataFrame(faixas)),
    ]:
        df.to_csv(DADOS / (arquivo + ".csv"), index=False)


if __name__ == "__main__":
    estudos()
