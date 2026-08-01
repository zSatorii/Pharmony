"""
Coordenadas aproximadas (lat, lng) de municipios colombianos comunes.
Se usa para ubicar las Sedes en el mapa automáticamente según su campo `ciudad`,
sin que el personal EPS tenga que indicar manualmente latitud/longitud.

Si una ciudad no está en este diccionario, se cae al centro del país (Bogotá)
como fallback visual y se loguea un aviso para que se pueda agregar.
"""

CIUDADES_COORDS = {
    "bogota": (4.7110, -74.0721),
    "bogotá": (4.7110, -74.0721),
    "mosquera": (4.7059, -74.2302),
    "madrid": (4.7325, -74.2667),
    "funza": (4.7173, -74.2098),
    "facatativa": (4.8133, -74.3550),
    "facatativá": (4.8133, -74.3550),
    "soacha": (4.5790, -74.2168),
    "chia": (4.8617, -74.0319),
    "chía": (4.8617, -74.0319),
    "zipaquira": (5.0214, -74.0094),
    "zipaquirá": (5.0214, -74.0094),
    "cajica": (4.9186, -74.0294),
    "cajicá": (4.9186, -74.0294),
    "medellin": (6.2442, -75.5812),
    "medellín": (6.2442, -75.5812),
    "cali": (3.4516, -76.5320),
    "barranquilla": (10.9639, -74.7964),
    "cartagena": (10.3910, -75.4794),
    "bucaramanga": (7.1193, -73.1227),
    "pereira": (4.8133, -75.6961),
    "manizales": (5.0703, -75.5138),
    "ibague": (4.4389, -75.2322),
    "ibagué": (4.4389, -75.2322),
    "santa marta": (11.2408, -74.1990),
    "villavicencio": (4.1420, -73.6266),
    "pasto": (1.2136, -77.2811),
    "monteria": (8.7575, -75.8877),
    "montería": (8.7575, -75.8877),
    "neiva": (2.9273, -75.2819),
    "armenia": (4.5339, -75.6811),
    "popayan": (2.4448, -76.6147),
    "popayán": (2.4448, -76.6147),
    "tunja": (5.5353, -73.3678),
    "valledupar": (10.4631, -73.2532),
}

FALLBACK_COORD = (4.7110, -74.0721)

def coords_para_ciudad(ciudad: str):
    if not ciudad:
        return FALLBACK_COORD
    clave = ciudad.strip().lower()
    return CIUDADES_COORDS.get(clave, FALLBACK_COORD)