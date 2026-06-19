import os
import logging
import base64
import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq
import base64

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = """Eres el asistente de cierre diario de la tienda Huawei Experience Store 1217 Angelópolis.

REGLAS ESTRICTAS:
- Responde ÚNICAMENTE con los reportes en el formato exacto indicado. CERO texto extra, CERO explicaciones, CERO cálculos mostrados, CERO clasificaciones adicionales.
- Usa EXACTAMENTE los emojis especificados, ni uno diferente.
- NO inventes datos de inventario. Si el usuario no los proporciona, pon — en esas líneas.

EQUIPO:
- Miguel (Subgerente), Arturo Aguilar (Asesor), Arnulfo (Asesor), Laura (Brand Specialist)

LECTURA DE IMAGEN:
La columna "Ventas netas" contiene montos BRUTOS (con IVA). Clasifica:
- Productos: smartphones, tablets, laptops, smartwatches
- Garantías: artículos con "GARANTÍA Y SEGURO"
- Accesorios: audífonos, correas, "PRODUCTOS VARIOS"
- Reparaciones: artículos con "REP FUERA DE GARANTÍA"
- Tickets = número total de transacciones en la imagen

CÁLCULOS (montos NETOS = bruto ÷ 1.16, redondeados sin decimales):
- CR = (Tickets ÷ Clientes) × 100
- Ticket Promedio = Neto Total ÷ Tickets
- Venta Potencial = Clientes × Ticket Promedio
- Attach Rate = (Seguros ÷ Equipos elegibles) × 100
- Acumulado mensual = acumulado_anterior + neto_productos_hoy
- Acumulado semanal = acumulado_semanal_anterior + neto_productos_hoy
- % PPTO = Acumulado mensual ÷ 1,832,000 × 100

FORMATO EXACTO — copia estos emojis exactamente:

1217 ANGELOPOLIS
🗓 Fecha: [DD/MM/YYYY]
💰 Venta total del día: $[neto total]
📱 Venta de equipos Huawei
🛍 Venta de producto $[neto productos]
📦 Cantidad de productos: [#]
🛡 Extra Cobertura Total
🛡️ Garantía vendidas: $[neto garantías] #[qty]
📊 Elegibles: [#] | Attach: [%]%
🔧 Venta Servicio Técnico
⚙️ Accesorios: $[neto accesorios] 📦 [#] productos
🛠️ Reparaciones: $[neto reparaciones]
👥 Clientes efectivos: [CR]%
📊 *Presupuesto (PPTO): $1,832,000
📈 Acumulado mensual: $[monto] ([%]%)
🗓️Acumulado semanal: $[monto]
📅 Resumen del día
🧾 Tickets: [#]
👨‍👩‍👧‍👦 Clientes: [#]
🛒 CR: [%]%
📄 Ticket promedio: $[monto]
💸 Venta potencial: $[monto]
👩🏽‍💻 Venta TMK: $0 | #️⃣ 0
🔄 Operación
♻️📲 Trade In: 0
👨🏻‍🏫 Training: ✅ Ok
🏪 Display: ✅ Ok
🚨 Productos con problema de inventario
📆 Artículo sin venta > 4 semanas:
[lista proporcionada por usuario o —]
📦 Artículo sin inventario (A):
[lista proporcionada por usuario o —]
💬 Comentarios:
[comentario del usuario o —]
✅ Plantilla Completa.

REPORTE DE GARANTÍAS (solo si hubo seguros, inmediatamente después del reporte principal):
Sin emojis. Montos BRUTOS.

1217
[#] seguros
Monto Total: $[bruto total]

[Nombre asesor] [#] seguros ($[bruto asesor])

Si faltan clientes o acumulados, pídelos antes de generar."""

# Inventario persistente en memoria
inventario_store = {
    "sin_inventario": [],
    "sin_venta": []
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hola! Soy el asistente de cierre diario HES 1217.\n\n"
        "📸 Mándame la foto del POS y escribe:\n"
        "• Clientes del día\n"
        "• Acumulado mensual anterior\n"
        "• Acumulado semanal anterior\n"
        "• Comentarios (opcional)\n\n"
        "Comandos de inventario:\n"
        "/inventario — ver lista actual\n"
        "/sininventario ITEM1, ITEM2 — actualizar sin stock\n"
        "/sinventa ITEM1, ITEM2 — actualizar sin venta >4 sem\n"
        "/limpiar — borrar listas"
    )

async def cmd_inventario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    si = inventario_store["sin_inventario"]
    sv = inventario_store["sin_venta"]
    msg = "📦 *Sin inventario (A):*\n"
    msg += "\n".join(si) if si else "—"
    msg += "\n\n📆 *Sin venta >4 semanas:*\n"
    msg += "\n".join(sv) if sv else "—"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def cmd_sininventario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = " ".join(context.args)
    if not texto:
        await update.message.reply_text("Uso: /sininventario ITEM1, ITEM2, ITEM3")
        return
    items = [i.strip() for i in texto.split(",") if i.strip()]
    inventario_store["sin_inventario"] = items
    await update.message.reply_text(f"✅ Sin inventario actualizado:\n" + "\n".join(items))

async def cmd_sinventa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = " ".join(context.args)
    if not texto:
        await update.message.reply_text("Uso: /sinventa ITEM1, ITEM2, ITEM3")
        return
    items = [i.strip() for i in texto.split(",") if i.strip()]
    inventario_store["sin_venta"] = items
    await update.message.reply_text(f"✅ Sin venta actualizado:\n" + "\n".join(items))

async def cmd_limpiar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inventario_store["sin_inventario"] = []
    inventario_store["sin_venta"] = []
    await update.message.reply_text("✅ Listas de inventario borradas.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import asyncio

    photo = update.message.photo[-1]
    file = await photo.get_file()
    file_bytes = await file.download_as_bytearray()

    if 'photos' not in context.user_data:
        context.user_data['photos'] = []
    context.user_data['photos'].append(bytes(file_bytes))

    caption = update.message.caption or ""
    if caption:
        context.user_data['extra_info'] = caption

    # Cancel previous timer if exists
    if 'timer' in context.user_data:
        context.user_data['timer'].cancel()

    # Wait 5 seconds for more photos before processing
    loop = asyncio.get_event_loop()
    timer = loop.call_later(5, lambda: asyncio.ensure_future(
        finalize_photos(update, context)
    ))
    context.user_data['timer'] = timer

    n = len(context.user_data['photos'])
    if n == 1:
        await update.message.reply_text(
            f"📸 Foto 1 recibida. Si hay más páginas mándalas ahora.\n"
            "Luego escribe:\n\n"
            "Clientes: [número]\n"
            "Acumulado mensual: [monto]\n"
            "Acumulado semanal: [monto]"
        )
    else:
        await update.message.reply_text(f"📸 Foto {n} recibida. Esperando más o datos del día...")

async def finalize_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'extra_info' in context.user_data:
        await process_report(update, context)
    # else wait for text with data

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'photos' not in context.user_data or not context.user_data['photos']:
        await update.message.reply_text("📸 Primero mándame la foto del POS.")
        return
    context.user_data['extra_info'] = update.message.text
    await process_report(update, context)

async def process_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Procesando... un momento.")
    try:
        photos = context.user_data.get('photos', [])
        extra_info = context.user_data.get('extra_info', '')
        today = datetime.date.today().strftime("%d/%m/%Y")

        si = inventario_store["sin_inventario"]
        sv = inventario_store["sin_venta"]
        inv_sin_stock = "\n".join(si) if si else "—"
        inv_sin_venta = "\n".join(sv) if sv else "—"

        prompt = f"""{SYSTEM_PROMPT}

Fecha de hoy: {today}
Información del usuario: {extra_info}

INVENTARIO GUARDADO (usa estos datos exactos, no inventes otros):
📦 Artículo sin inventario (A): {inv_sin_stock}
📆 Artículo sin venta >4 semanas: {inv_sin_venta}

Analiza {'las ' + str(len(photos)) + ' imágenes' if len(photos) > 1 else 'la imagen'} del POS y genera los reportes completos."""

        content = []
        for pb in photos:
            image_b64 = base64.b64encode(pb).decode()
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}})
        content.append({"type": "text", "text": prompt})

        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role": "user", "content": content}],
            max_tokens=4096
        )

        result = response.choices[0].message.content
        await update.message.reply_text(result)
        context.user_data.pop('photos', None)
        context.user_data.pop('extra_info', None)
        context.user_data.pop('timer', None)

    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}\n\nIntenta de nuevo.")

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()

if __name__ == "__main__":
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    threading.Thread(target=run_health_server, daemon=True).start()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("inventario", cmd_inventario))
    app.add_handler(CommandHandler("sininventario", cmd_sininventario))
    app.add_handler(CommandHandler("sinventa", cmd_sinventa))
    app.add_handler(CommandHandler("limpiar", cmd_limpiar))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling(drop_pending_updates=True)
