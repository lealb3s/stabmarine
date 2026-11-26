"""Benchmarks independentes. Execute python verificacao.py para reproduzir os CSV."""

from pathlib import Path
import numpy as np
import pandas as pd
from geometria import ANG, caixa, cruzadas
from estabilidade import avaliar
from cenarios import registro, PESOS, TANQUES

PASTA = Path(__file__).parent / "validacao"


def controle(L, B, D, T, cond):
    casco = caixa(L, B, D)
    v = L * B * T
    vs = np.array([v])
    return avaliar(casco, vs, cruzadas(casco, vs), cond, rho=1.0)


def comparacao(ang, ref, calc):
    d = np.abs(calc - ref)
    erro = np.full_like(d, np.nan)
    np.divide(100 * d, np.abs(ref), out=erro, where=np.abs(ref) > 1e-12)
    return pd.DataFrame(
        {
            "Banda (°)": ang,
            "Referência (m)": ref,
            "App (m)": calc,
            "Dif. absoluta (m)": d,
            "Dif. (%)": erro,
        }
    )


def validar():
    # Prisma 4 x 4 m com meia seção imersa. O tanque quadrado também está meio cheio.
    cond = {
        "pesos": registro(
            PESOS, [("Base", 69.5, 5, 0, 1.25), ("Peso móvel", 10, 5, 0.8, 2.0)]
        ),
        "tanques": registro(TANQUES, [("Água", 1, 1, 1, 5, 0, 0.5, 1, 50)]),
    }
    m, g, _, _ = controle(10, 4, 4, 2, cond)
    kg = (69.5 * 1.25 + 10 * 2 + 0.5 * 0.75) / 80
    fsc = 1 / (12 * 80)
    refs = [10 * (2 - 1) / 80, 10 * 0.8 / 80, fsc, 1 + 4**2 / (12 * 2) - kg - fsc]
    calc = [
        m["KG (m)"] - (69.5 * 1.25 + 10 + 0.5 * 0.75) / 80,
        m["TCG (m)"],
        m["FSC (m)"],
        m["GM corr. (m)"],
    ]
    param = pd.DataFrame(
        {
            "Grandeza": ["ΔKG (m)", "ΔTCG (m)", "FSC (m)", "GM corrigido (m)"],
            "Manual": refs,
            "App": calc,
            "Dif. absoluta": np.abs(np.array(refs) - calc),
        }
    )
    a = np.array([-90.0, -30.0, 0.0, 30.0, 90.0])
    rad = np.deg2rad(a)
    # A ±90°, o centro do volume ocupa o centro vertical da seção (e do tanque).
    kn = np.where(abs(a) == 90, 2 * np.sin(rad), 0.0)
    shift = np.where(abs(a) == 90, 0.25 * np.sin(rad), 0.0)
    w = abs(a) < 90
    kn[w] = np.sin(rad[w]) * (1 + 16 / 24 * (1 + np.tan(rad[w]) ** 2 / 2))
    shift[w] = np.sin(rad[w]) * (1 / (12 * 0.5)) * (1 + np.tan(rad[w]) ** 2 / 2)
    ref = kn - kg * np.sin(rad) - 0.1 * np.cos(rad) - 0.5 / 80 * shift
    v1 = comparacao(a, ref, np.interp(a, ANG, g["GZ (m)"]))
    v2cond = {
        "pesos": registro(PESOS, [("Embarcação leve", 96, 6, 0, 1.6)]),
        "tanques": [],
    }
    _, g, _, _ = controle(12, 4, 5, 2, v2cond)
    a = np.arange(-20.0, 21.0, 2.0)
    rad = np.deg2rad(a)
    # Tupper, Introduction to Naval Architecture, cap. 4, fórmula de costados verticais.
    ref = np.sin(rad) * (1 + 16 / 24 - 1.6 + 16 / 48 * np.tan(rad) ** 2)
    v2 = comparacao(a, ref, np.interp(a, ANG, g["GZ (m)"]))
    return param, v1, v2


if __name__ == "__main__":
    for n, df in zip(["balanco", "analitica", "tupper"], validar()):
        df.to_csv(PASTA / (n + ".csv"), index=False)
        print(n, df.iloc[:, -2 if n != "balanco" else -1].max())
