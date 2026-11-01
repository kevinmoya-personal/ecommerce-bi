"""Genera los datos ficticios del dashboard de e-commerce (semilla fija, reproducible)."""
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
INICIO, CORTE = pd.Timestamp("2024-01-01"), pd.Timestamp("2026-09-30")
N_CLIENTES, N_PEDIDOS = 4000, 26000
DATA = Path(__file__).resolve().parents[1] / "data"

CATALOGO = {
    "Tecnología": ["Audífonos Bluetooth", "Teclado Mecánico", "Mouse Inalámbrico", "Cargador USB-C", "Parlante Portátil", "Smartwatch Fit"],
    "Hogar": ["Lámpara LED", "Set de Sábanas", "Organizador Modular", "Cafetera Prensa", "Juego de Ollas"],
    "Moda": ["Chaqueta Impermeable", "Tenis Urbanos", "Morral Antirrobo", "Gafas de Sol", "Camiseta Básica"],
    "Belleza": ["Crema Hidratante", "Sérum Vitamina C", "Kit de Brochas", "Protector Solar"],
    "Deportes": ["Mat de Yoga", "Bandas Elásticas", "Botella Térmica", "Mancuernas Ajustables"],
}
CIUDADES = {"Bogotá": ("Andina", .34), "Medellín": ("Andina", .18), "Cali": ("Pacífica", .14), "Barranquilla": ("Caribe", .11),
            "Cartagena": ("Caribe", .06), "Bucaramanga": ("Andina", .07), "Pereira": ("Andina", .05), "Santa Marta": ("Caribe", .05)}
CANALES = {"Orgánico": (.30, .028), "Pago Social": (.25, .016), "Búsqueda Paga": (.22, .024), "Email": (.13, .052), "Referidos": (.10, .041)}
ETAPAS = [("Visitas", 1, None), ("Vista de producto", 2, .52), ("Carrito", 3, .24), ("Checkout", 4, .58), ("Compra", 5, None)]


def main() -> None:
    rng = np.random.default_rng(SEED)
    DATA.mkdir(exist_ok=True)

    filas = []
    pid = 1
    for cat, nombres in CATALOGO.items():
        for n in nombres:
            precio = round(float(rng.uniform(35, 420))) * 1000.0
            filas.append((f"P{pid:03d}", n, cat, precio, round(precio * rng.uniform(.48, .72), -2)))
            pid += 1
    productos = pd.DataFrame(filas, columns=["producto_id", "producto", "categoria", "precio_lista", "costo_unitario"])

    canales = pd.DataFrame({"canal": list(CANALES)})

    ciudades = list(CIUDADES)
    prob_ciudad = [CIUDADES[c][1] for c in ciudades]
    clientes = pd.DataFrame({"cliente_id": [f"C{i:05d}" for i in range(1, N_CLIENTES + 1)]})
    clientes["ciudad"] = rng.choice(ciudades, N_CLIENTES, p=prob_ciudad)
    clientes["region"] = clientes["ciudad"].map(lambda c: CIUDADES[c][0])

    dias = pd.date_range(INICIO, CORTE)
    tendencia = np.linspace(1, 1.7, len(dias))
    estacional = np.where(dias.month.isin([11, 12]), 1.65, 1) * np.where(dias.month.isin([1, 2]), .8, 1)
    peso_dia = tendencia * estacional
    fechas_pedido = rng.choice(dias, N_PEDIDOS, p=peso_dia / peso_dia.sum())

    # Pocos clientes concentran muchas compras: así el RFM y la recompra se ven realistas.
    afinidad = rng.pareto(1.3, N_CLIENTES) + .15
    pedidos = pd.DataFrame({
        "pedido_id": [f"O{i:06d}" for i in range(1, N_PEDIDOS + 1)],
        "fecha": pd.to_datetime(fechas_pedido),
        "cliente_id": rng.choice(clientes["cliente_id"], N_PEDIDOS, p=afinidad / afinidad.sum()),
        "canal": rng.choice(list(CANALES), N_PEDIDOS, p=[v[0] for v in CANALES.values()]),
        "estado": rng.choice(["Completado", "Devuelto", "Cancelado"], N_PEDIDOS, p=[.91, .05, .04]),
    }).sort_values("fecha", ignore_index=True)

    popularidad = rng.dirichlet(np.full(len(productos), 1.2))
    lineas = pedidos.loc[pedidos.index.repeat(rng.choice([1, 2, 3], N_PEDIDOS, p=[.68, .24, .08]))].reset_index(drop=True)
    idx = rng.choice(len(productos), len(lineas), p=popularidad)
    lineas["producto_id"] = productos["producto_id"].to_numpy()[idx]
    lineas["cantidad"] = rng.choice([1, 2, 3], len(lineas), p=[.78, .17, .05])
    lineas["descuento_pct"] = rng.choice([0, .05, .10, .20], len(lineas), p=[.6, .18, .15, .07])
    precio = productos["precio_lista"].to_numpy()[idx]
    lineas["ingreso"] = (lineas["cantidad"] * precio * (1 - lineas["descuento_pct"])).round(0)
    lineas["costo"] = (lineas["cantidad"] * productos["costo_unitario"].to_numpy()[idx]).round(0)
    lineas = lineas.drop_duplicates(["pedido_id", "producto_id"], ignore_index=True)
    lineas = lineas[["pedido_id", "fecha", "cliente_id", "producto_id", "canal", "estado", "cantidad", "descuento_pct", "ingreso", "costo"]]

    # El embudo parte de los pedidos reales: la etapa "Compra" cuadra con los pedidos completados.
    completados = pedidos[pedidos["estado"] == "Completado"]
    compras = completados.groupby([completados["fecha"].dt.to_period("M").dt.to_timestamp(), "canal"]).size()
    embudo = []
    for (mes, canal), n in compras.items():
        conv = CANALES[canal][1] * rng.uniform(.92, 1.08)
        visitas = n / conv
        producto = visitas * ETAPAS[1][2] * rng.uniform(.97, 1.03)
        carrito = producto * ETAPAS[2][2] * rng.uniform(.95, 1.05)
        checkout = max(carrito * ETAPAS[3][2] * rng.uniform(.95, 1.05), n * 1.05)
        for (etapa, orden, _), valor in zip(ETAPAS, [visitas, producto, carrito, checkout, n]):
            embudo.append((mes, canal, etapa, orden, int(round(valor))))
    embudo = pd.DataFrame(embudo, columns=["mes", "canal", "etapa", "orden_etapa", "usuarios"])

    calendario = pd.DataFrame({"fecha": dias})
    calendario["anio"] = calendario["fecha"].dt.year
    calendario["trimestre"] = "T" + calendario["fecha"].dt.quarter.astype(str)
    calendario["periodo"] = calendario["fecha"].dt.strftime("%Y-%m")

    fecha_fmt = {"date_format": "%Y-%m-%d", "index": False, "encoding": "utf-8"}
    productos.to_csv(DATA / "dim_producto.csv", index=False, encoding="utf-8")
    canales.to_csv(DATA / "dim_canal.csv", index=False, encoding="utf-8")
    clientes.to_csv(DATA / "dim_cliente.csv", index=False, encoding="utf-8")
    calendario.to_csv(DATA / "dim_calendario.csv", **fecha_fmt)
    lineas.to_csv(DATA / "fact_ventas.csv", **fecha_fmt)
    embudo.to_csv(DATA / "fact_embudo.csv", **fecha_fmt)

    ok = lineas[lineas["estado"] == "Completado"]
    print(f"lineas={len(lineas)} pedidos={lineas['pedido_id'].nunique()} clientes_con_compra={ok['cliente_id'].nunique()}")
    print(f"ventas={ok['ingreso'].sum():,.0f} ticket={ok['ingreso'].sum() / ok['pedido_id'].nunique():,.0f}")
    print(f"compras_embudo={embudo.loc[embudo['etapa'] == 'Compra', 'usuarios'].sum()} pedidos_completados={len(completados)}")


if __name__ == "__main__":
    main()
