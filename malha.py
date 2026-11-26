"""Malha KN do conjunto Damen. Execute python malha.py após revisar as cotas."""

from pathlib import Path
from hashlib import sha256
from io import BytesIO
import pandas as pd
import numpy as np
from geometria import ANG, Casco, cruzadas

DADOS = Path(__file__).parent / "dados"


def calcular_malha(cotas):
    casco = Casco(pd.read_csv(BytesIO(cotas)))
    volumes = np.linspace(0.03, 0.97, 31) * casco.cap
    v_ref = 69.978 / 1.025
    if volumes[0] < v_ref < volumes[-1]:
        volumes = np.unique(np.r_[volumes, v_ref])
    return volumes, cruzadas(casco, volumes)


def carregar(cotas, arquivo):
    if arquivo.exists():
        with np.load(arquivo, allow_pickle=False) as r:
            if (
                str(r["sha256"]) == sha256(cotas).hexdigest()
                and np.array_equal(r["banda"], ANG)
                and r["kn"].shape == (len(r["volumes"]), len(ANG))
            ):
                return r["volumes"], r["kn"]
    return calcular_malha(cotas)


if __name__ == "__main__":
    cotas = (DADOS / "damen.csv").read_bytes()
    volumes, kn = calcular_malha(cotas)
    np.savez_compressed(
        DADOS / "cruzadas_damen.npz",
        volumes=volumes,
        kn=kn,
        sha256=sha256(cotas).hexdigest(),
        banda=ANG,
    )
