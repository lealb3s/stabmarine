"""Balanço de pesos, movimento do líquido, interpolação de KN e análise de GZ."""

from functools import lru_cache
import numpy as np
import pandas as pd
from geometria import ANG, S, C, caixa
from cenarios import PESOS, TANQUES


@lru_cache(maxsize=128)
def deslocamento_liquido(b, h, fracao):
    # Projeção horizontal do centro do líquido em cada banda; o comprimento cancela.
    retangulo = caixa(1, b, h)
    pos = np.array([retangulo.kn(b * h * fracao, a) for a in ANG[ANG >= 0]])
    return np.r_[-pos[:0:-1], pos] - h * fracao * S / 2


def conferir(casco, rows, cols):
    df = pd.DataFrame(rows, columns=cols)
    if df.empty:
        return df
    if (
        df[cols[0]].isna().any()
        or df[cols[0]].astype(str).str.strip().eq("").any()
        or df[cols[0]].duplicated().any()
    ):
        raise ValueError("Cada linha precisa de um nome único na respectiva tabela.")
    df[cols[1:]] = df[cols[1:]].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(df[cols[1:]].to_numpy(float)).all():
        raise ValueError("Preencha todos os campos numéricos das linhas utilizadas.")
    for r in df.itertuples(index=False):
        if cols == PESOS:
            if r.Massa_t <= 0:
                raise ValueError(f"{r.Item} precisa ter massa positiva.")
            limites = [r.X_m, r.X_m, r.Z_m, r.Z_m, abs(r.Y_m)]
        else:
            if min(r.L_m, r.B_m, r.H_m, r.Rho_t_m3) <= 0 or not 0 <= r.Nivel_pct <= 100:
                raise ValueError(
                    f"Confira dimensões, densidade e enchimento de {r.Tanque}."
                )
            limites = [
                r.X_m - r.L_m / 2,
                r.X_m + r.L_m / 2,
                r.Fundo_m,
                r.Fundo_m + r.H_m,
                abs(r.Y_m) + r.B_m / 2,
            ]
        x0, x1, z0, z1, b = limites
        if x0 < casco.x[0] or x1 > casco.x[-1] or z0 < casco.z[0] or z1 > casco.z[-1]:
            raise ValueError(
                f"{r[0]} ultrapassa os limites longitudinais ou verticais do casco."
            )
        xs = np.r_[x0, casco.x[(casco.x > x0) & (casco.x < x1)], x1]
        zs = np.r_[z0, casco.z[(casco.z > z0) & (casco.z < z1)], z1]
        if b > min(casco.largura(x, z) for x in xs for z in zs) + 1e-8:
            raise ValueError(
                f"{r[0]} ultrapassa a meia-boca disponível na posição indicada."
            )
    return df


def area(gz, a, b):
    interno = (ANG > a) & (ANG < b)
    pontos = np.r_[a, ANG[interno], b]
    return np.trapezoid(np.interp(pontos, ANG, gz), np.deg2rad(pontos))


def raizes(gz):
    roots = []
    for i, (x, g) in enumerate(zip(ANG, gz)):
        if abs(g) < 1e-10:
            roots.append(x)
        elif i and gz[i - 1] * g < 0 and abs(gz[i - 1]) >= 1e-10:
            roots.append(x - (x - ANG[i - 1]) * g / (g - gz[i - 1]))
    return np.array(roots)


def avaliar(
    casco,
    volumes,
    malha,
    cond,
    rho=1.025,
    limites=(-100.0, 100.0),
    intervalo=(0.0, 40.0),
):
    p = conferir(casco, cond["pesos"], PESOS)
    t = conferir(casco, cond["tanques"], TANQUES)
    total = np.zeros(4)
    for r in p.itertuples(index=False):
        total += r.Massa_t * np.array([1.0, r.X_m, r.Y_m, r.Z_m])
    move = np.zeros(len(ANG))
    fsm = 0.0
    lista = list(t.itertuples(index=False))
    for i, r in enumerate(lista):
        for q in lista[:i]:
            if (
                abs(r.X_m - q.X_m) < (r.L_m + q.L_m) / 2 - 1e-8
                and abs(r.Y_m - q.Y_m) < (r.B_m + q.B_m) / 2 - 1e-8
                and max(r.Fundo_m, q.Fundo_m)
                < min(r.Fundo_m + r.H_m, q.Fundo_m + q.H_m) - 1e-8
            ):
                raise ValueError(f"Os tanques {q.Tanque} e {r.Tanque} se sobrepõem.")
        f = r.Nivel_pct / 100
        m = r.Rho_t_m3 * r.L_m * r.B_m * r.H_m * f
        total += m * np.array([1.0, r.X_m, r.Y_m, r.Fundo_m + r.H_m * f / 2])
        if 0 < f < 1:
            fsm += r.Rho_t_m3 * r.L_m * r.B_m**3 / 12
            move += m * deslocamento_liquido(r.B_m, r.H_m, f)
    delta = total[0]
    v = delta / rho
    if not volumes[0] <= v <= volumes[-1]:
        raise ValueError(
            f"Deslocamento {delta:.3f} t fora da tabela KN ({volumes[0] * rho:.3f} a {volumes[-1] * rho:.3f} t)."
        )
    xg, yg, kg = total[1:] / delta
    h = casco.hidro(v)
    if h["KML"] <= kg:
        raise ValueError(
            "Equilíbrio longitudinal incompatível com a hipótese de trim nulo."
        )
    trim = np.rad2deg(np.arctan((xg - h["LCB"]) / (h["KML"] - kg)))
    if abs(trim) > 1:
        raise ValueError(
            f"Trim inicial estimado de {trim:.2f}° excede o limite didático de 1°. Redistribua os pesos em X ou utilize um modelo com trim livre."
        )
    kn = np.array([np.interp(v, volumes, col) for col in malha.T])
    fixo = kn - kg * S - yg * C
    gz = fixo - move / delta
    roots = raizes(gz)
    lo, hi = limites
    knots = np.unique(np.r_[lo, ANG[(ANG > lo) & (ANG < hi)], hi])
    values = np.interp(knots, ANG, gz)
    roots = roots[(roots >= lo) & (roots <= hi)]
    estaveis = [
        r
        for r in roots
        if lo < r < hi
        and np.interp(r + 0.001, ANG, gz) > 0
        and np.interp(r - 0.001, ANG, gz) < 0
    ]
    eq = min(estaveis, key=abs) if estaveis else np.nan
    bounds = np.unique(np.r_[lo, roots, hi])
    sinais = {s: [] for s in ["+", "−"]}
    for a, b in zip(bounds, bounds[1:]):
        y = np.interp((a + b) / 2, ANG, gz)
        if abs(y) > 1e-12:
            sinais["+" if y > 0 else "−"].append(f"{a:.2f} a {b:.2f}")
    a, b = intervalo
    permitido = lo <= a < b <= hi
    metrics = {
        "Δ (t)": delta,
        "∇ (m³)": v,
        "T (m)": h["T"],
        "LCB (m)": h["LCB"],
        "KB (m)": h["KB"],
        "KM (m)": h["KM"],
        "LCG (m)": xg,
        "TCG (m)": yg,
        "KG (m)": kg,
        "FSC (m)": fsm / delta,
        "GM corr. (m)": h["KM"] - kg - fsm / delta,
        "Equilíbrio (°)": eq,
        "GZ máx. (m)": values.max(),
        "Banda do máximo (°)": knots[np.argmax(values)],
        "Área (m·rad)": area(gz, a, b) if permitido else np.nan,
        "Momento transversal (t·m)": delta * yg,
        "Trim estimado (°)": trim,
    }
    return (
        metrics,
        pd.DataFrame(
            {"Banda (°)": ANG, "KN (m)": kn, "GZ (m)": gz, "GZ líquido fixo (m)": fixo}
        ),
        roots,
        sinais,
    )
