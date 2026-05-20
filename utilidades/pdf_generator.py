from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas


def _dibujar_texto_largo(c, x, y, texto, max_chars=80, paso=0.5 * cm):
    while texto:
        c.drawString(x, y, texto[:max_chars])
        texto = texto[max_chars:]
        y -= paso
    return y


def generar_pdf(datos, output_path):
    """Genera un PDF A4 con resguardo arriba y etiqueta troquelada abajo."""
    w, h = A4
    c = canvas.Canvas(output_path, pagesize=A4)

    margen = 2 * cm
    y = h - margen

    c.setFont("Helvetica-Bold", 18)
    c.drawString(margen, y, "RepairHub")
    y -= 0.6 * cm
    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(margen, y, "Servicio técnico de reparaciones — Tel: 600 000 000")
    y -= 1.5 * cm

    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(margen, y, datos['codigo'])

    c.setFont("Helvetica", 10)
    fecha_str = datos['fecha'].strftime('%d/%m/%Y %H:%M')
    c.drawRightString(w - margen, y, f"Fecha: {fecha_str}")
    y -= 1.5 * cm

    c.setStrokeColorRGB(0.8, 0.8, 0.8)
    c.setLineWidth(0.5)
    c.line(margen, y, w - margen, y)
    y -= 1 * cm

    c.setFont("Helvetica-Bold", 11)
    c.drawString(margen, y, "DATOS DEL CLIENTE")
    y -= 0.6 * cm
    c.setFont("Helvetica", 10)
    c.drawString(margen, y, f"Nombre: {datos['nombre_cliente']}")
    y -= 0.5 * cm
    contacto = []
    if datos.get('telefono'):
        contacto.append(f"Tel: {datos['telefono']}")
    if datos.get('email'):
        contacto.append(f"Email: {datos['email']}")
    c.drawString(margen, y, " | ".join(contacto))
    y -= 1 * cm

    c.setFont("Helvetica-Bold", 11)
    c.drawString(margen, y, "DATOS DEL DISPOSITIVO")
    y -= 0.6 * cm
    c.setFont("Helvetica", 10)
    c.drawString(margen, y, f"Tipo: {datos['tipo_dispositivo']}    Marca: {datos.get('marca', '-')}    Modelo: {datos.get('modelo', '-')}")
    y -= 0.8 * cm

    c.setFont("Helvetica-Bold", 11)
    c.drawString(margen, y, "AVERÍA / MOTIVO DE ENTRADA")
    y -= 0.6 * cm
    c.setFont("Helvetica", 10)
    y = _dibujar_texto_largo(c, margen, y, datos['averia'])

    if datos.get('observaciones'):
        y -= 0.3 * cm
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margen, y, "OBSERVACIONES")
        y -= 0.6 * cm
        c.setFont("Helvetica", 10)
        y = _dibujar_texto_largo(c, margen, y, datos['observaciones'])

    y -= 0.5 * cm
    c.setFont("Helvetica", 7)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    condiciones = [
        "CONDICIONES DE SERVICIO:",
        "1. El plazo de recogida es de 30 días desde la notificación de finalización.",
        "2. El presupuesto no incluye IVA salvo que se indique expresamente.",
        "3. RepairHub no se hace responsable de datos almacenados en el dispositivo.",
        "4. Este resguardo es necesario para la recogida del dispositivo."
    ]
    for linea in condiciones:
        c.drawString(margen, y, linea)
        y -= 0.4 * cm

    y -= 0.8 * cm
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 9)
    c.drawString(margen, y, "Firma del cliente: ___________________________")
    c.drawRightString(w - margen, y, f"Fecha: {datos['fecha'].strftime('%d/%m/%Y')}")

    corte_y = 9 * cm
    c.setDash(3, 3)
    c.setStrokeColorRGB(0.6, 0.6, 0.6)
    c.setLineWidth(0.5)
    c.line(margen, corte_y, w - margen, corte_y)
    c.setFont("Helvetica", 7)
    c.setFillColorRGB(0.6, 0.6, 0.6)
    c.drawCentredString(w / 2, corte_y + 0.2 * cm, "✂ Cortar por aquí — Etiqueta para el dispositivo")
    c.setDash()

    etiqueta_y = corte_y - 0.5 * cm
    etiqueta_h = 7.5 * cm
    etiqueta_x = margen

    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(1)
    c.rect(etiqueta_x, etiqueta_y - etiqueta_h, w - 2 * margen, etiqueta_h)

    ey = etiqueta_y - 0.8 * cm

    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(etiqueta_x + 0.5 * cm, ey, datos['codigo'])

    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(w - margen - 0.5 * cm, ey, "RepairHub")
    ey -= 1 * cm

    c.setFont("Helvetica", 11)
    c.drawString(etiqueta_x + 0.5 * cm, ey, f"Cliente: {datos['nombre_cliente']}")
    ey -= 0.7 * cm

    dispositivo = f"{datos['tipo_dispositivo']} — {datos.get('marca', '')} {datos.get('modelo', '')}".strip()
    c.drawString(etiqueta_x + 0.5 * cm, ey, f"Dispositivo: {dispositivo}")
    ey -= 0.7 * cm

    averia_corta = datos['averia'][:50] + ('...' if len(datos['averia']) > 50 else '')
    c.drawString(etiqueta_x + 0.5 * cm, ey, f"Avería: {averia_corta}")
    ey -= 0.7 * cm

    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(etiqueta_x + 0.5 * cm, ey, f"Entrada: {datos['fecha'].strftime('%d/%m/%Y %H:%M')}")

    c.save()
    return output_path
