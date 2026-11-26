"""Integração das seções simétricas em repouso longitudinal, com banda prescrita."""

import numpy as np
import pandas as pd

ANG = np.arange(-100.0, 101.0, 2.0)
RAD = np.deg2rad(ANG)
S, C = np.sin(RAD), np.cos(RAD)


class Casco:
    def __init__(self, tabela):
        p = (
            tabela.pivot(index="x_m", columns="z_m", values="meia_boca_m")
            .sort_index()
            .sort_index(axis=1)
        )
        self.x, self.z, self.b = (
            p.index.to_numpy(float),
            p.columns.to_numpy(float),
            p.to_numpy(float),
        )
        if not np.isfinite(self.x).all() or not np.isfinite(self.z).all():
            raise ValueError(
                "As posições das balizas e das linhas d’água devem ser finitas."
            )
        if (
            min(self.b.shape) < 2
            or not np.isfinite(self.b).all()
            or (self.b < 0).any()
            or not self.b.max()
        ):
            raise ValueError(
                "Forneça ao menos duas balizas e duas alturas, com uma meia-boca válida em cada ponto."
            )
        self.y = np.column_stack((self.b, -self.b[:, ::-1]))
        self.h = np.tile(np.r_[self.z, self.z[::-1]], (len(self.x), 1))
        # Pesos trapezoidais longitudinais, inclusive para balizas desigualmente espaçadas.
        dx = np.diff(self.x)
        self.w = (np.r_[0, dx] + np.r_[dx, 0]) / 2
        self.cap = np.trapezoid(2 * self.b, self.z, axis=1) @ self.w

    def largura(self, x, z):
        return np.interp(x, self.x, [np.interp(z, self.z, b) for b in self.b])

    def girar(self, graus):
        a = np.deg2rad(graus)
        return self.y * np.cos(a) + self.h * np.sin(a), self.h * np.cos(
            a
        ) - self.y * np.sin(a)

    def imerso(self, u, v, nivel, momentos=False):
        # Integrais de contorno. A aresta de fechamento sobre v=nivel tem v relativo nulo.
        v0 = v - nivel
        v1 = np.roll(v0, -1, axis=1)
        u1 = np.roll(u, -1, axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            f = np.divide(v0, v0 - v1, out=np.zeros_like(v0), where=v0 != v1)
        corte = u + f * (u1 - u)
        a, b = np.where(v0 <= 0, u, corte), np.minimum(v0, 0)
        c, d = np.where(v1 <= 0, u1, corte), np.minimum(v1, 0)
        cross = a * d - c * b
        area = cross.sum(axis=1) / 2
        volume = area @ self.w
        if not momentos:
            return volume
        mu = ((a + c) * cross).sum(axis=1) @ self.w / 6
        mv = ((b + d) * cross).sum(axis=1) @ self.w / 6
        return mu / volume, mv / volume + nivel, (area * self.x) @ self.w / volume

    def flutuar(self, volume, graus):
        if not (0 < volume < self.cap):
            raise ValueError(
                f"Volume fora da geometria fechada (0 a {self.cap:.3f} m³)."
            )
        u, v = self.girar(graus)
        lo, hi = v.min(), v.max()
        for _ in range(38):
            h = (lo + hi) / 2
            if self.imerso(u, v, h) < volume:
                lo = h
            else:
                hi = h
        h = (lo + hi) / 2
        return h, *self.imerso(u, v, h, True)

    def hidro(self, volume):
        t, _, kb, lcb = self.flutuar(volume, 0)
        b = np.array([np.interp(t, self.z, row) for row in self.b])
        bm = (2 * b**3 / 3) @ self.w / volume
        aw = 2 * b @ self.w
        xf = (2 * b * self.x) @ self.w / aw
        bml = (2 * b * (self.x - xf) ** 2) @ self.w / volume
        return dict(T=t - self.z[0], KB=kb, LCB=lcb, KM=kb + bm, KML=kb + bml)

    def kn(self, volume, graus):
        return self.flutuar(volume, graus)[1]


def cruzadas(casco, volumes):
    linhas = []
    for v in volumes:
        kn = [casco.kn(v, a) for a in ANG[ANG >= 0]]
        linhas.append(np.r_[-np.array(kn[:0:-1]), kn])
    return np.array(linhas)


def caixa(L, B, D):
    return Casco(
        pd.DataFrame(
            [(x, z, B / 2) for x in [0, L] for z in [0, D]],
            columns=["x_m", "z_m", "meia_boca_m"],
        )
    )
