"""Salvar e recuperar sessões em JSON, sem serialização de código."""

import json
import numpy as np
import pandas as pd
from geometria import Casco
from estabilidade import conferir
from cenarios import PESOS, TANQUES


def salvar(nome, rho, tabela, volumes, casos):
    payload = {
        "versao": 1,
        "casco": nome,
        "rho": rho,
        "cotas": tabela.to_dict("records"),
        "volumes_kn": volumes.tolist(),
        "condicoes": casos,
    }
    return json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2).encode(
        "utf-8"
    )


def ler(data):
    p = json.loads(data)
    if not isinstance(p, dict) or p.get("versao") != 1:
        raise ValueError("Selecione um projeto salvo no AP1.5.")
    tabela = pd.DataFrame(p["cotas"])[["x_m", "z_m", "meia_boca_m"]].astype(float)
    casco = Casco(tabela)
    rho = float(p["rho"])
    vs = np.asarray(p["volumes_kn"], float)
    if (
        not 0.1 <= rho <= 2
        or vs.ndim != 1
        or len(vs) < 2
        or not np.isfinite(vs).all()
        or not (np.diff(vs) > 0).all()
        or vs[0] <= 0
        or vs[-1] >= casco.cap
    ):
        raise ValueError("Confira a densidade e o intervalo de volumes KN.")
    casos = p["condicoes"]
    if not isinstance(casos, dict) or not casos:
        raise ValueError("Projeto sem condições de carga.")
    for chave, cond in casos.items():
        if not chave.strip():
            raise ValueError("Condição sem nome.")
        for k, cols in [("pesos", PESOS), ("tanques", TANQUES)]:
            cond[k] = conferir(casco, cond[k], cols).to_dict("records")
    return str(p["casco"]), rho, tabela, vs, casos
