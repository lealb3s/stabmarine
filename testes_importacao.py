"""Regressões da conversão de coordenadas e do importador de geometrias."""

import unittest
from io import BytesIO
import numpy as np
import pandas as pd
import trimesh

from cad import eixos, offsets, triangulos
from entrada import COLUNAS, abas, cotas, matriz, normalizar, reconhecer_pontos
from geometria import Casco


class ImportacaoTest(unittest.TestCase):
    def test_excel_multiplas_abas(self):
        mem = BytesIO()
        with pd.ExcelWriter(mem, engine="openpyxl") as xl:
            pd.DataFrame([["ensaio"]]).to_excel(
                xl, sheet_name="Resumo", header=False, index=False
            )
            pd.DataFrame(
                [(x, z, 2.0) for x in (0.0, 12.0) for z in (0.0, 5.0)], columns=COLUNAS
            ).to_excel(xl, sheet_name="Cotas", index=False, startrow=3)
        self.assertEqual(abas(mem.getvalue(), "teste.xlsx"), ["Resumo", "Cotas"])
        t = cotas(mem.getvalue(), "teste.xlsx", "Cotas")
        self.assertAlmostEqual(Casco(t).cap, 240.0)

    def test_matriz_transposta_e_unidades(self):
        raw = pd.DataFrame(
            [
                ["Z", 0, 12000],
                [0, "4.000,0", "4000"],
                [1000, 4000, 4000],
                ["fim", None, None],
            ]
        )
        d = matriz(raw, 1, 3, "Z", 0, [1, 2], [0, 12000])
        c = Casco(normalizar(d, ("mm", "mm", "mm"), "Boca total"))
        self.assertAlmostEqual(c.cap, 48.0)

    def test_pontos_lacunas_e_bordos(self):
        raw = pd.DataFrame(
            [
                ["Y(mm)", "altura (cm)", "X (m)"],
                [-500, 0, 0],
                [500, 0, 0],
                [500, 50, 0],
                [500, 100, 0],
                [500, 0, 4],
                [500, 100, 4],
            ]
        )
        d = reconhecer_pontos(raw)
        with self.assertRaisesRegex(ValueError, "Falta meia-boca"):
            normalizar(d, ("m", "cm", "mm"), "Y em relação à linha de centro")
        c = Casco(
            normalizar(
                d,
                ("m", "cm", "mm"),
                "Y em relação à linha de centro",
                "Interpolar em Z entre valores conhecidos",
            )
        )
        self.assertAlmostEqual(c.cap, 4.0)

    def test_caixa_cad_e_simetria(self):
        caixa = trimesh.creation.box(extents=[12000, 4000, 5000])
        for tipo in ["stl", "obj"]:
            content = caixa.export(file_type=tipo)
            if isinstance(content, str):
                content = content.encode()
            t = eixos(triangulos(content, "teste." + tipo), 0, 2, 0.001)
            c = Casco(offsets(t, 7, 7, 0, "Casco completo"))
            self.assertAlmostEqual(c.cap, 240.0)
            with self.assertRaises(ValueError):
                offsets(t, 7, 7, 0.5, "Casco completo")
            lado = t[t[:, :, 1].min(axis=1) > 1]
            np.testing.assert_allclose(
                offsets(lado, 7, 7, 0, "Meio casco em Y positivo").meia_boca_m, 2.0
            )


if __name__ == "__main__":
    unittest.main()
