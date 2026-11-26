"""Regressões de conservação, dados de entrada e operações. Execute python testes.py."""

import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from cenarios import exemplos, transferir, NOMES
from estabilidade import avaliar, area
from geometria import Casco, ANG
from entrada import cotas
from projeto import salvar, ler
from verificacao import validar


class EstabilidadeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = Path(__file__).parent / "dados"
        cls.tabela = cotas((d / "damen.csv").read_bytes(), "casco.csv")
        cls.casco = Casco(cls.tabela)
        with np.load(d / "cruzadas_damen.npz") as r:
            cls.vs, cls.kn = r["volumes"], r["kn"]

    def calc(self, c):
        return avaliar(self.casco, self.vs, self.kn, c)

    def test_casos(self):
        r = [self.calc(c)[0] for c in exemplos().values()]
        np.testing.assert_allclose([v["Δ (t)"] for v in r], 69.978)
        self.assertAlmostEqual(r[1]["TCG (m)"], 5 * 1.8 / 69.978)
        self.assertGreater(r[4]["Equilíbrio (°)"], 4)
        self.assertLess(r[4]["GM corr. (m)"], r[0]["GM corr. (m)"])
        self.assertAlmostEqual(r[5]["Equilíbrio (°)"], 0)

    def test_tanques(self):
        c = exemplos()[NOMES[0]]
        novo = transferir(c, "Água • ré", "Água • vante", 1.5)
        self.assertEqual(c["tanques"][1]["Nivel_pct"], 100)
        self.assertAlmostEqual(self.calc(c)[0]["Δ (t)"], self.calc(novo)[0]["Δ (t)"])
        np.testing.assert_allclose(
            self.calc(novo)[1]["GZ (m)"], self.calc(exemplos()[NOMES[3]])[1]["GZ (m)"]
        )
        with self.assertRaises(ValueError):
            transferir(c, "Água • ré", "Água • vante", 4)

    def test_desembarque_e_limites(self):
        c = exemplos()[NOMES[0]]
        m, g, *_ = self.calc(c)
        c["pesos"][-1]["Massa_t"] -= 2
        n, g2, *_ = self.calc(c)
        self.assertAlmostEqual(m["Δ (t)"] - n["Δ (t)"], 2)
        self.assertFalse(np.allclose(g["KN (m)"], g2["KN (m)"]))
        self.assertLess(n["T (m)"], m["T (m)"])
        c["pesos"][0]["Massa_t"] = 300
        with self.assertRaisesRegex(ValueError, "fora da tabela KN"):
            self.calc(c)
        c = exemplos()[NOMES[0]]
        c["pesos"][0]["X_m"] = 13
        with self.assertRaisesRegex(ValueError, "Trim"):
            self.calc(c)

    def test_controles(self):
        b, v1, v2 = validar()
        self.assertLess(b["Dif. absoluta"].max(), 1e-9)
        for df in (v1, v2):
            self.assertLess(df["Dif. absoluta (m)"].max(), 1e-9)
        self.assertAlmostEqual(area(np.ones_like(ANG), 1, 18), np.deg2rad(17))

    def test_projeto(self):
        cs = exemplos()
        _, rho, tabela, vs, out = ler(salvar("Damen", 1.025, self.tabela, self.vs, cs))
        self.assertEqual(out, cs)
        self.assertEqual(rho, 1.025)
        np.testing.assert_allclose(vs, self.vs)
        pd.testing.assert_frame_equal(tabela, self.tabela)


if __name__ == "__main__":
    unittest.main()
