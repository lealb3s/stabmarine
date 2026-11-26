"""Inventário em t e m. Cada cenário é uma cópia independente."""

from copy import deepcopy

PESOS = ["Item", "Massa_t", "X_m", "Y_m", "Z_m"]
TANQUES = [
    "Tanque",
    "L_m",
    "B_m",
    "H_m",
    "X_m",
    "Y_m",
    "Fundo_m",
    "Rho_t_m3",
    "Nivel_pct",
]
NOMES = [
    "1 · Inicial",
    "2 · Carga a boreste",
    "3 · Elevação",
    "4 · Superfície livre",
    "5 · Combinada",
    "6 · Correção",
]


def registro(cols, rows):
    return [dict(zip(cols, row)) for row in rows]


def exemplos():
    pesos = registro(
        PESOS,
        [
            ("Embarcação leve", 48, 8, 0, 1.25),
            ("Equipamentos", 4, 10.5, 0, 1.2),
            ("Suprimentos", 1.5, 11.5, 0, 1.4),
            ("Tripulação", 0.16, 9.5, 0, 1.8),
            ("Pessoal industrial", 1.28, 11.5, 0, 1.8),
            ("Carga do porão", 5, 6, 0, 2.0),
        ],
    )
    tanques = registro(
        TANQUES,
        [
            ("Combustível", 3, 2.4, 1.15, 6, 0, 0.85, 0.85, 100.0),
            ("Água • ré", 2, 1.5, 1, 8.6, 0, 0.65, 1.0, 100.0),
            ("Água • vante", 2, 1.5, 1, 10.7, 0, 0.65, 1.0, 0.0),
        ],
    )
    casos = {}
    for i, nome in enumerate(NOMES):
        p, t = deepcopy(pesos), deepcopy(tanques)
        if i in (1, 4):
            p[-1]["Y_m"] = 1.8
        if i in (2, 4):
            p[1]["Z_m"] = 2.55
        if i in (3, 4):
            t[1]["Nivel_pct"] = t[2]["Nivel_pct"] = 50.0
        if i == 5:
            p[1]["Z_m"] = 1.0
            p[-1]["Z_m"] = 1.25
        casos[nome] = {"pesos": p, "tanques": t}
    return casos


def transferir(cond, origem, destino, volume):
    if origem == destino or volume <= 0:
        raise ValueError("Escolha dois tanques diferentes e um volume positivo.")
    novo = deepcopy(cond)
    tanques = {r["Tanque"]: r for r in novo["tanques"]}
    a, b = tanques[origem], tanques[destino]
    if abs(a["Rho_t_m3"] - b["Rho_t_m3"]) > 1e-9:
        raise ValueError("A transferência requer líquidos de mesma densidade.")
    for r, sinal in [(a, -1), (b, 1)]:
        cap = r["L_m"] * r["B_m"] * r["H_m"]
        pct = r["Nivel_pct"] + 100 * sinal * volume / cap
        if not -1e-9 <= pct <= 100 + 1e-9:
            raise ValueError(
                "O volume excede o conteúdo da origem ou o espaço livre do destino."
            )
        r["Nivel_pct"] = min(100.0, max(0.0, pct))
    return novo
