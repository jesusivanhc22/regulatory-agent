# ==============================
# DOMINIO SANITARIO
# (Farmacias, medicamentos, NOMs sanitarias, COFEPRIS)
# ==============================

HEALTH_KEYWORDS = [
    # NOMs clave para farmacias privadas
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
    "receta retenida",
    "receta con código de barras",
    # Antimicrobianos y controlados
    "antimicrobiano",
    "antimicrobianos",
    "antibiótico",
    "psicotrópico",
    "estupefaciente",
    "sustancia controlada",
    # Operación sanitaria farmacia
    "farmacovigilancia",
    "tecnovigilancia",
    "insumos para la salud",
    "registro sanitario",
    "dispositivo médico",
    "responsable sanitario",
    "aviso de funcionamiento",
    "licencia sanitaria",
    "aviso de responsable sanitario",
    # Sistema y trazabilidad
    "sistema computarizado validado",
    "sistema computarizado",
    "trazabilidad",
    "registro electrónico",
    "cadena de frío",
    "control de temperatura",
    # Buenas prácticas farmacia privada
    "buenas prácticas de dispensación",
    "buenas prácticas de almacenamiento",
    "buenas prácticas de distribución",
    "buenas prácticas de farmacia",
    # FEUM
    "farmacopea de los estados unidos mexicanos",
    "FEUM",
    # Alertas y residuos
    "alerta sanitaria",
    "alertamiento sanitario",
    "residuos peligrosos",
    "RPBI",
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
    # Obligaciones generales
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
    # Obligaciones específicas de farmacia/sanitarias
    "deberá validar",
    "deberá notificar",
    "deberá almacenar",
    "deberá llevar registro",
    "deberá llevar un registro",
    "deberá llevar una bitácora",
    "deberá verificar",
    "deberá dispensar",
    "deberá controlar",
    "deberá monitorear",
    "deberá documentar",
    "deberá garantizar",
    "deberá mantener",
    "obligado a reportar",
    "obligado a notificar",
    "obligado a registrar",
]
