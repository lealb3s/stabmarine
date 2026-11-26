"""Extração de meias-bocas por interseção transversal de uma malha CAD."""

from io import BytesIO
from pathlib import Path
import numpy as np
import pandas as pd
from entrada import COLUNAS


def documento_rhino(data):
    import rhino3dm as rh

    doc = rh.File3dm.FromByteArray(data)
    if doc is None:
        raise ValueError("O arquivo 3DM não pôde ser lido.")
    return doc


def objetos_rhino(data):
    doc = documento_rhino(data)
    objetos = {}
    for i, obj in enumerate(doc.Objects):
        if obj.Attributes.IsInstanceDefinitionObject:
            continue
        kind = type(obj.Geometry).__name__
        if kind not in (
            "Mesh",
            "Brep",
            "Extrusion",
            "Surface",
            "NurbsSurface",
            "InstanceReference",
        ):
            continue
        try:
            layer = doc.Layers.FindIndex(obj.Attributes.LayerIndex)
        except IndexError:
            layer = None
        objetos[i] = (
            f"{i + 1} · {layer.Name if layer else 'Camada'} · {obj.Attributes.Name or kind}"
        )
    return objetos, doc.Settings.ModelUnitSystem.name


def triangulos_rhino(data, indices):
    import rhino3dm as rh

    doc = documento_rhino(data)
    partes = []
    for i in indices:
        obj = doc.Objects[i]
        geo = obj.Geometry
        if isinstance(geo, rh.Mesh):
            malhas = [geo]
        elif isinstance(geo, rh.Brep):
            malhas = [f.GetMesh(rh.MeshType.Render) for f in geo.Faces]
        elif isinstance(geo, rh.Extrusion):
            malhas = [geo.GetMesh(rh.MeshType.Render)]
        else:
            malhas = []
        if not malhas or any(
            m is None or not len(m.Vertices) or not m.Faces.Count for m in malhas
        ):
            raise ValueError(
                f"O objeto {i + 1} não contém uma malha utilizável. No Rhino, selecione o casco, execute _Mesh e exporte a malha selecionada em STL, OBJ ou 3DM."
            )
        for m in malhas:
            v = np.array([(p.X, p.Y, p.Z) for p in m.Vertices])
            faces = np.asarray([m.Faces[j] for j in range(m.Faces.Count)])
            quads = faces[:, 2] != faces[:, 3]
            partes.append(v[np.vstack([faces[:, :3], faces[quads][:, [0, 2, 3]]])])
    if not partes:
        raise ValueError("Selecione a geometria do casco.")
    return np.concatenate(partes)


def triangulos(data, nome, indices=()):
    ext = Path(nome).suffix.lower()[1:]
    if ext == "3dm":
        t = triangulos_rhino(data, indices)
    else:
        import trimesh

        cena = trimesh.load_scene(
            BytesIO(data),
            file_type=ext,
            process=False,
            **({"skip_materials": True} if ext == "obj" else {}),
        )
        mesh = cena.to_mesh()
        t = np.asarray(mesh.triangles)
    if not t.size or t.ndim != 3 or t.shape[1:] != (3, 3) or not np.isfinite(t).all():
        raise ValueError(
            "O arquivo deve conter faces de malha com coordenadas finitas."
        )
    return t


def eixos(t, longitudinal, vertical, escala, inverter_x=False, inverter_z=False):
    if longitudinal == vertical:
        raise ValueError("Os eixos longitudinal e vertical devem ser diferentes.")
    iy = next(i for i in range(3) if i not in (longitudinal, vertical))
    a = t[:, :, [longitudinal, iy, vertical]].copy() * escala
    if inverter_x:
        a[:, :, 0] *= -1
    if inverter_z:
        a[:, :, 2] *= -1
    a[:, :, 0] -= a[:, :, 0].min()
    a[:, :, 2] -= a[:, :, 2].min()
    return a


def offsets(t, nx, nz, centro, modo):
    """Raio em Y para cada par X/Z; rejeita interseções incompatíveis com o modelo."""
    mn = t.min(axis=(0, 1))
    mx = t.max(axis=(0, 1))
    L, B, H = mx - mn
    if modo != "Casco completo":
        B = 2 * max(abs(mx[1] - centro), abs(mn[1] - centro))
    if min(L, B, H) <= 0:
        raise ValueError("A geometria precisa ter extensão nos três eixos.")
    xs = np.linspace(mn[0], mx[0], nx)
    zs = np.linspace(mn[2], mx[2], nz)
    # Amostrar pelo interior nas bordas evita dupla contagem de faces coplanares.
    xx = np.clip(xs, mn[0] + L * 1e-8, mx[0] - L * 1e-8)
    zz = np.clip(zs, mn[2] + H * 1e-8, mx[2] - H * 1e-8)
    if (
        modo == "Meio casco em Y positivo"
        and mn[1] < centro - B * 1e-5
        or modo == "Meio casco em Y negativo"
        and mx[1] > centro + B * 1e-5
    ):
        raise ValueError(
            "O bordo escolhido cruza o plano de centro. Confira o modo e a posição de Y central."
        )
    p = t[:, 0]
    u = t[:, 1] - p
    v = t[:, 2] - p
    det = u[:, 0] * v[:, 2] - v[:, 0] * u[:, 2]
    frente = t[:, :, 0].min(axis=1)
    tras = t[:, :, 0].max(axis=1)
    saida = np.zeros((nx, nz))
    for i, x in enumerate(xx):
        ok = (abs(det) > 1e-14 * L * H) & (frente <= x) & (tras >= x)
        a, b, d, r = p[ok], u[ok], v[ok], det[ok]
        dx = x - a[:, 0]
        for j, z in enumerate(zz):
            dz = z - a[:, 2]
            s = (dx * d[:, 2] - dz * d[:, 0]) / r
            h = (dz * b[:, 0] - dx * b[:, 2]) / r
            dentro = (s >= -1e-10) & (h >= -1e-10) & (s + h <= 1 + 1e-10)
            hits = np.sort((a[:, 1] + s * b[:, 1] + h * d[:, 1])[dentro] - centro)
            if not hits.size:
                continue
            # Suprimir apenas interseções coincidentes (arestas partilhadas).
            hits = hits[np.r_[True, np.diff(hits) > B * 1e-7]]
            lados = hits[abs(hits) > B * 1e-7]
            if not lados.size:
                continue
            if modo == "Casco completo":
                if (
                    len(lados) != 2
                    or lados[0] * lados[1] >= 0
                    or abs(lados.sum()) > 0.01 * B
                ):
                    raise ValueError(
                        f"Seção incompatível com o monocasco simétrico em X={xs[i]:.3f}, Z={zs[j]:.3f} m. Confira eixos, plano central, bordo e objetos selecionados."
                    )
                saida[i, j] = (lados[1] - lados[0]) / 2
            else:
                if len(lados) != 1:
                    raise ValueError(
                        "Múltiplos contornos no mesmo bordo. Selecione apenas o costado externo."
                    )
                saida[i, j] = abs(lados[0])
    if not saida.any():
        raise ValueError(
            "Nenhuma seção utilizável foi encontrada. Confira os eixos do modelo."
        )
    return pd.DataFrame(
        {
            COLUNAS[0]: np.repeat(xs, nz),
            COLUNAS[1]: np.tile(zs, nx),
            COLUNAS[2]: saida.ravel(),
        }
    )
