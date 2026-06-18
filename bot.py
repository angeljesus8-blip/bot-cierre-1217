import os
import logging
import re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import google.generativeai as genai

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

SYSTEM_PROMPT = """Eres el asistente de cierre diario de la tienda Huawei Experience Store 1217 Angelópolis.

EQUIPO (nombres fijos, nunca cambies):
- Miguel (Subgerente)
- Arturo Aguilar (Asesor)
- Arnulfo (Asesor)
- Laura (Brand Specialist)

PASO 1 — LEE LA IMAGEN
La columna "Ventas netas" en la imagen contiene montos BRUTOS (con IVA).
Clasifica cada artículo:
- Productos: smartphones, tablets, laptops, smartwatches
- Garantías: artículos que digan "GARANTÍA Y SEGURO"
- Accesorios: audífonos, correas, "PRODUCTOS VARIOS"
- Reparaciones: artículos que digan "REP FUERA DE GARANTÍA"

PASO 2 — GENERA EL REPORTE PRINCIPAL
Usa montos NETOS (bruto ÷ 1.16), redondeados sin decimales.
PPTO mensual fijo: $1,832,000

Fórmulas:
- CR = (Tickets ÷ Clientes) × 100
- Ticket Promedio = Neto Total ÷ Tickets
- Venta Potencial = Clientes × Ticket Promedio
- Attach Rate = (Seguros vendidos ÷ Equipos elegibles) × 100
- Acumulado mensual = acumulado_anterior + neto_productos_hoy
- Acumulado semanal = acumulado_semanal_anterior + neto_productos_hoy

Formato EXACTO del reporte principal:

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
[lista o —]
📦 Artículo sin inventario (A):
[lista o —]
💬 Comentarios:
[comentario o —]
✅ Plantilla Completa.

PASO 3 — REPORTE DE GARANTÍAS (solo si hubo seguros)
Sin emojis. Montos BRUTOS (con IVA).

1217
[#] seguros
Monto Total: $[bruto total garantías]

[Nombre asesor] [#] seguros ($[bruto del asesor])
(solo asesores con al menos 1 seguro)

Responde SIEMPRE con los dos reportes listos para copiar. Si faltan datos (clientes, acumulados), pídelos antes de generar."""

WAITING_INFO = 1

user_data_store = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hola! Soy el asistente de cierre diario HES 1217.\n\n"
        "📸 Mándame la foto del POS y luego dime:\n"
        "• Clientes del día\n"
        "• Acumulado mensual anterior\n"
        "• Acumulado semanal anterior\n"
        "• Comentarios (opcional)\n\n"
        "Puedes mandar todo en un solo mensaje de texto después de la foto."
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()
    file_bytes = await file.download_as_bytearray()

    context.user_data['photo_bytes'] = bytes(file_bytes)

    caption = update.message.caption or ""
    if caption:
        context.user_data['extra_info'] = caption
        await process_report(update, context)
    else:
        await update.message.reply_text(
            "📸 Foto recibida. Ahora dime:\n\n"
            "*Clientes:* [número]\n"
            "*Acumulado mensual:* [monto]\n"
            "*Acumulado semanal:* [monto]\n"
            "*Comentarios:* [opcional]",
            parse_mode='Markdown'
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'photo_bytes' not in context.user_data:
        await update.message.reply_text("📸 Primero mándame la foto del POS.")
        return

    context.user_data['extra_info'] = update.message.text
    await process_report(update, context)

async def process_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Procesando... un momento.")

    try:
        photo_bytes = context.user_data.get('photo_bytes')
        extra_info = context.user_data.get('extra_info', '')

        import datetime
        today = datetime.date.today().strftime("%d/%m/%Y")

        image_part = {
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": __import__('base64').b64encode(photo_bytes).decode()
            }
        }

        prompt = f"""{SYSTEM_PROMPT}

Fecha de hoy: {today}
Información adicional del usuario: {extra_info}

Analiza la imagen del POS y genera los reportes completos."""

        response = model.generate_content([prompt, image_part])

        result = response.text

        # Split into two reports if there are guarantees
        parts = result.split("1217\n")

        if len(parts) >= 2:
            reporte_principal = parts[0].strip()
            reporte_garantias = "1217\n" + parts[1].strip()

            await update.message.reply_text(reporte_principal)
            await update.message.reply_text("─" * 20)
            await update.message.reply_text(reporte_garantias)
        else:
            await update.message.reply_text(result)

        context.user_data.clear()

    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text(f"❌ Error procesando la imagen: {str(e)}\n\nIntenta de nuevo.")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling()

if __name__ == "__main__":
    main()
