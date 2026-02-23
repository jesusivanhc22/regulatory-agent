# ==============================
# DOMINIO SANITARIO
# (Farmacias, medicamentos, NOMs sanitarias, COFEPRIS)
# ==============================

HEALTH_KEYWORDS = [
    # NOMs clave para farmacias
    "NOM-059-SSA",
    "NOM-072-SSA",
    "NOM-176-SSA",
    "NOM-001-SSA",
    "NOM-024",
    "NOM-004",
    "NOM-220",
    "NOM-240",
    "NOM-241",
    # Instituciones y reguladores
    "Secretaría de Salud",
    "COFEPRIS",
    # Farmacias y medicamentos
    "farmacopea",
    "suplemento para establecimientos",
    "venta y suministro de medicamentos",
    "farmacia",
    "medicamento",
    "sustancia activa",
    "medicamentos controlados",
    "receta electrónica",
    "receta médica",
    # Operación sanitaria
    "expediente clínico",
    "farmacovigilancia",
    "insumos para la salud",
    "registro sanitario",
    "dispositivo médico",
    "control sanitario",
    "buenas prácticas de fabricación",
    "buenas prácticas de almacenamiento",
    "buenas prácticas de distribución",
]

# ==============================
# DOMINIO FISCAL
# (CFDI, facturación, carta porte, obligaciones tributarias)
# ==============================

FISCAL_KEYWORDS = [
    "servicio de administración tributaria",
    "CFDI",
    "Anexo 20",
    "factura electrónica",
    "factura global",
    "DIOT",
    "devolución de IVA",
    "Resolución Miscelánea",
    "carta porte",
    "complemento de pago",
    "complemento carta porte",
    "comprobante de traslado",
    "traslado de mercancías",
    "retención de impuestos",
    "contabilidad electrónica",
    "comprobante fiscal",
]

# ==============================
# DOMINIO RETAIL
# ==============================

RETAIL_KEYWORDS = [
    "comercio al por menor",
    "establecimientos comerciales",
    "PROFECO",
    "precio máximo",
    "precio al consumidor",
]

# ==============================
# REGIÓN FRONTERIZA
# ==============================

BORDER_KEYWORDS = [
    "franja fronteriza",
    "región fronteriza norte",
    "región fronteriza sur",
    "IVA 8%",
    "estímulo fiscal frontera",
]

# ==============================
# MONEDA EXTRANJERA / DIVISAS
# ==============================

CURRENCY_KEYWORDS = [
    "moneda extranjera",
    "divisas",
    "tipo de cambio",
    "dólar estadounidense",
    "operación cambiaria",
]

# ==============================
# OBLIGACIÓN OPERATIVA
# (Solo frases compuestas — "deberá" suelto matchea con todo el DOF)
# ==============================

OBLIGATION_KEYWORDS = [
    "deberá registrar",
    "deberá reportar",
    "deberá conservar",
    "deberá implementar",
    "deberá facturar",
    "deberá declarar",
    "deberá emitir",
    "deberá cancelar",
    "deberá cumplir",
    "deberá contar con",
    "obligación fiscal",
    "estará obligado",
    "se obliga a",
]
