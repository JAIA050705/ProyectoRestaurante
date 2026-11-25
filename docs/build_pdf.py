#!/usr/bin/env python3
"""Builds docs/Documentacion_AWS.pdf (the written deliverable of the AWS free project)."""
import json, os
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle,
                                Image, PageBreak, Preformatted, KeepTogether)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_URL = os.environ.get("REPO_URL", "")          # set REPO_URL=... to print the repository link on the cover
OUT = os.path.join(HERE, "Documentacion_AWS.pdf")

INK = colors.HexColor("#1f2430"); BLUE = colors.HexColor("#1d4f91"); GRID = colors.HexColor("#c9d1dc")
SOFT = colors.HexColor("#eef3f9"); CODEBG = colors.HexColor("#f3f4f6")

ss = getSampleStyleSheet()
body = ParagraphStyle("body", parent=ss["Normal"], fontName="Helvetica", fontSize=10, leading=14.5, textColor=INK, spaceAfter=6)
small = ParagraphStyle("small", parent=body, fontSize=8.6, leading=11.5, spaceAfter=0)
cell = ParagraphStyle("cell", parent=body, fontSize=8.6, leading=11.2, spaceAfter=0)
cellb = ParagraphStyle("cellb", parent=cell, fontName="Helvetica-Bold")
h1 = ParagraphStyle("h1", parent=body, fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=BLUE, spaceBefore=4, spaceAfter=8)
h2 = ParagraphStyle("h2", parent=body, fontName="Helvetica-Bold", fontSize=12, leading=16, textColor=BLUE, spaceBefore=10, spaceAfter=4)
code = ParagraphStyle("code", parent=body, fontName="Courier", fontSize=8.6, leading=11.2, backColor=CODEBG, borderPadding=(5, 6, 5, 6),
                      spaceBefore=4, spaceAfter=9, leftIndent=4, rightIndent=4)
bullet = ParagraphStyle("bullet", parent=body, leftIndent=14, bulletIndent=3, spaceAfter=3)
cap = ParagraphStyle("cap", parent=small, textColor=colors.HexColor("#555b66"), spaceBefore=3, spaceAfter=10)

def P(t, s=body): return Paragraph(t, s)
def B(items): return [Paragraph(i, bullet, bulletText="\u2022") for i in items]
def C(t): return Preformatted(t, code)
def table(rows, widths, header=True, zebra=True):
    data = [[Paragraph(str(c), cellb if (header and r == 0) else cell) for c in row] for r, row in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.5, GRID), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
          ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5)]
    if header: st.append(("BACKGROUND", (0, 0), (-1, 0), SOFT))
    t.setStyle(TableStyle(st)); return t

def footer(canvas, doc):
    canvas.saveState(); canvas.setFont("Helvetica", 8); canvas.setFillColor(colors.HexColor("#666b75"))
    canvas.drawString(0.8 * inch, 0.5 * inch, "Restaurant Review Platform API - Despliegue en AWS")
    canvas.drawRightString(letter[0] - 0.8 * inch, 0.5 * inch, f"P\u00e1gina {doc.page}")
    canvas.restoreState()

doc = BaseDocTemplate(OUT, pagesize=letter, leftMargin=0.8 * inch, rightMargin=0.8 * inch, topMargin=0.75 * inch,
                      bottomMargin=0.8 * inch, title="Restaurant Review Platform API - Despliegue en AWS",
                      author="Arturo Leobardo Jaramillo Iniguez")
doc.addPageTemplates([PageTemplate(id="p", frames=[Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")], onPage=footer)])
W = doc.width
S = []

# ------------------------------------------------------------------ cover
S += [Spacer(1, 1.2 * inch), P("Restaurant Review Platform API", ParagraphStyle("t", parent=h1, fontSize=28, leading=33)),
      P("Despliegue en AWS con infraestructura como c\u00f3digo", ParagraphStyle("st", parent=h2, fontSize=15, leading=20)),
      Spacer(1, 0.3 * inch),
      P("Proyecto Libre - Computaci\u00f3n Sustentable<br/>Categor\u00eda: web. Proyecto individual."),
      Spacer(1, 0.25 * inch),
      P("<b>Alumno:</b> Arturo Leobardo Jaramillo \u00cd\u00f1iguez (c\u00f3digo 223977273)<br/>"
        "<b>Carrera:</b> Ingenier\u00eda en Ciencias Computacionales, CUTonal\u00e1, Universidad de Guadalajara<br/>"
        "<b>Profesor:</b> V\u00edctor Hugo Vega Fregoso<br/><b>Fecha:</b> 22 de noviembre de 2026")]
if REPO_URL:
    S.append(P(f"<b>Repositorio Git:</b> {REPO_URL}"))
S += [Spacer(1, 0.4 * inch), P("Resumen", h2),
      P("La API REST de rese\u00f1as de restaurantes (Java, Jakarta REST, GlassFish 8, MySQL 8.4, JWT) y su interfaz web "
        "se despliegan en una instancia EC2 de AWS creada por completo con un script de Python (boto3), sin usar la consola. "
        "Un solo comando crea la base (llave SSH, firewall, bucket S3, secretos cifrados) y otro lanza el servidor, que se "
        "instala solo. El mismo WAR que corre en GlassFish local es el que se despliega en la nube."),
      P("Se prob\u00f3 la resiliencia con fallas provocadas a prop\u00f3sito: ca\u00edda de GlassFish, ca\u00edda de MySQL, versiones "
        "defectuosas del WAR, carga concurrente y la p\u00e9rdida total del servidor. En todos los casos el sistema se recuper\u00f3 y los "
        "datos quedaron intactos. El costo estimado de operarlo 24/7 fuera de la capa gratuita es de unos 247 USD al a\u00f1o; "
        "apagarlo fuera de horario lo baja a unos 129 USD."),
      P("Contenido", h2)]
S += B(["1. Gu\u00eda de Despliegue", "2. Diagrama de Arquitectura", "3. Justificaci\u00f3n de Decisiones",
        "4. An\u00e1lisis de Costos", "5. Pruebas de Resiliencia", "6. Limitaciones y trabajo futuro", "7. Fuentes"])
S.append(PageBreak())

# ------------------------------------------------------------------ 1 guide
S += [P("1. Gu\u00eda de Despliegue", h1),
      P("Todo se ejecuta desde la carpeta <font name='Courier'>infra</font> del repositorio, en la PC del administrador. "
        "Cada comando es idempotente: si se repite no duplica recursos."),
      P("Requisitos", h2)]
S += B(["Python 3.10 o superior y <font name='Courier'>pip install -r requirements.txt</font> (instala boto3).",
        "Una cuenta de AWS Academy Learner Lab con el laboratorio iniciado y sus credenciales temporales (dependen de la sesi\u00f3n, duran unas 4 horas).",
        "El WAR exportado desde Eclipse (<i>Export, WAR file</i>) con el nombre <font name='Courier'>RestaurantReviewAPI.war</font>.",
        "OpenSSH en la PC (viene con Windows 10 y 11), solo para las pruebas de resiliencia y diagn\u00f3stico."])
S += [P("Paso 0. Credenciales", h2),
      P("En AWS Academy, <i>AWS Details, AWS CLI, Show</i>. En el s\u00edmbolo del sistema de Windows:"),
      C("set AWS_ACCESS_KEY_ID=...\nset AWS_SECRET_ACCESS_KEY=...\nset AWS_SESSION_TOKEN=...\naws sts get-caller-identity"),
      P("Paso 1. Verificaci\u00f3n previa (Fase 0)", h2),
      P("<font name='Courier'>python preflight.py</font> revisa, sin crear nada, qu\u00e9 permite hacer el laboratorio "
        "(identidad, EC2, S3, SSM, CloudWatch, perfil de instancia). Con <font name='Courier'>--write-tests</font> crea y borra recursos "
        "diminutos para confirmar los permisos de escritura. En el laboratorio real dio 24 pruebas correctas y una falla esperada "
        "(la API de precios est\u00e1 bloqueada, por eso los precios de este documento se verificaron en las p\u00e1ginas oficiales)."),
      P("Paso 2. La base", h2),
      C("python deploy.py base --war C:\\ruta\\RestaurantReviewAPI.war"),
      P("Crea la llave SSH (<font name='Courier'>rr-project-key.pem</font>, no se sube a Git), el grupo de seguridad (puerto 80 abierto, "
        "puerto 22 solo desde la IP actual del administrador), el bucket de S3 con acceso p\u00fablico bloqueado, los tres secretos "
        "(contrase\u00f1a de MySQL, contrase\u00f1a de root y secreto JWT, generados al azar y guardados cifrados en SSM Parameter Store) "
        "y sube el esquema de la base y el WAR."),
      P("Paso 3. El servidor", h2),
      C("python deploy.py server"),
      P("Lanza la instancia, le asigna una Elastic IP, crea las alarmas de CloudWatch y espera hasta que la API responde 200 "
        "(unos 4 a 10 minutos). El servidor se configura solo al arrancar (<font name='Courier'>bootstrap/user_data.sh</font>): instala "
        "Java 25, Docker y nginx; levanta MySQL 8.4 en un contenedor con los datos en un disco EBS aparte; descarga GlassFish 8.0.4; "
        "carga el esquema o el \u00faltimo respaldo; y activa los servicios. Termina imprimiendo la URL "
        "<font name='Courier'>http://&lt;IP&gt;/RestaurantReviewAPI/</font>."),
      P("Paso 4. Verificaci\u00f3n", h2),
      C("python deploy.py status"),
      P("Debe mostrar <font name='Courier'>API answers: 200</font>. Despu\u00e9s se abre la URL en el navegador y se registra un usuario "
        "nuevo (los usuarios de ejemplo del esquema no tienen una contrase\u00f1a v\u00e1lida)."),
      P("Operaci\u00f3n diaria", h2)]
S.append(table([
    ["Comando", "Qu\u00e9 hace"],
    ["python deploy.py update --war RUTA", "Sube una nueva versi\u00f3n. El servidor la despliega solo en menos de un minuto."],
    ["python deploy.py rollback", "Vuelve a la versi\u00f3n anterior del WAR sin entrar por SSH."],
    ["python deploy.py stop / start", "Apaga el servidor cuando nadie lo usa y lo enciende despu\u00e9s. Los datos y la IP se conservan."],
    ["python deploy.py deployer", "Instala en el servidor la \u00faltima versi\u00f3n del script desplegador y lo destraba."],
    ["python resilience_tests.py", "Corre las pruebas de resiliencia y genera resilience_report.md. Con --include-server-loss agrega la prueba destructiva."],
    ["python destroy.py", "Muestra lo que va a borrar y pide confirmaci\u00f3n. Solo toca recursos con la etiqueta Project=restaurant-review."],
], [2.3 * inch, W - 2.3 * inch]))
S += [Spacer(1, 6), P("Problemas encontrados al construirlo", h2),
      P("Estos fallos aparecieron en el laboratorio real y ya est\u00e1n corregidos en los scripts; se dejan documentados porque "
        "son los que m\u00e1s probablemente le pasen a quien lo repita.")]
S.append(table([
    ["S\u00edntoma", "Causa", "Soluci\u00f3n"],
    ["La carga de datos fallaba con <i>Can't connect to local MySQL server through socket</i>.",
     "La imagen de MySQL arranca primero un servidor temporal que solo escucha en un socket. Un ping por socket responde antes de tiempo.",
     "El script espera por TCP (127.0.0.1:3306), donde solo escucha el servidor final, y exige 3 respuestas seguidas."],
    ["GlassFish mostraba <i>UnsupportedClassVersionError</i> y la API respond\u00eda 404.",
     "El WAR se compil\u00f3 con Java 25 y el servidor ten\u00eda Java 21.",
     "El servidor instala Amazon Corretto 25, la misma versi\u00f3n con la que se compila."],
    ["Un WAR v\u00e1lido se marcaba como rechazado y no se reintentaba.",
     "El primer despliegue ocurr\u00eda mientras GlassFish todav\u00eda arrancaba y el fallo se interpretaba como WAR defectuoso.",
     "El desplegador espera a que GlassFish est\u00e9 listo y solo rechaza un WAR si hay una versi\u00f3n buena a la cual volver."],
    ["SSH daba <i>Connection timed out</i> al d\u00eda siguiente.", "Cambi\u00f3 la IP p\u00fablica del administrador y el firewall solo permit\u00eda la anterior.",
     "<font name='Courier'>python deploy.py base</font> actualiza la regla del puerto 22."],
    ["Al iniciar una nueva sesi\u00f3n del laboratorio no hab\u00eda servidor.", "El laboratorio borr\u00f3 los recursos entre sesiones.",
     "Se recrea todo con <font name='Courier'>base</font> y <font name='Courier'>server</font> (prueba de que el despliegue es reproducible)."],
], [1.9 * inch, 2.35 * inch, W - 4.25 * inch]))
S.append(PageBreak())

# ------------------------------------------------------------------ 2 architecture
S += [P("2. Diagrama de Arquitectura", h1),
      Image(os.path.join(HERE, "img", "arch.png"), width=W, height=W * 0.6),
      P("Figura 1. Arquitectura desplegada en us-east-1.", cap),
      P("El tr\u00e1fico del usuario entra por una Elastic IP al puerto 80, donde nginx lo atiende: limita los intentos de login a 5 por "
        "segundo por direcci\u00f3n y reenv\u00eda el resto a GlassFish (puerto 8080). GlassFish ejecuta el mismo WAR que corre en local, que "
        "contiene la API y la interfaz web, y se conecta a MySQL por 127.0.0.1. MySQL corre en un contenedor Docker y guarda sus datos en un "
        "disco EBS de 10 GB separado del disco del sistema. MySQL no es accesible desde fuera de la instancia."),
      P("Fuera de la instancia hay tres servicios administrados. <b>S3</b> guarda las versiones del WAR, el esquema inicial y los respaldos "
        "de la base. <b>SSM Parameter Store</b> guarda los secretos cifrados y el nombre del WAR vigente (<font name='Courier'>war_key</font>). "
        "<b>CloudWatch</b> vigila los chequeos de estado de la instancia y la reinicia o recupera si fallan. La PC del administrador "
        "solo usa la API de AWS con boto3; no hay nada instalado a mano en el servidor."),
      Image(os.path.join(HERE, "img", "flow.png"), width=W * 0.70, height=W * 0.70 * 1736 / 2284),
      P("Figura 2. Flujo de una actualizaci\u00f3n: el servidor consulta el par\u00e1metro cada 60 segundos (modelo pull), sin abrir el "
        "puerto de administraci\u00f3n de GlassFish a Internet.", cap)]

# ------------------------------------------------------------------ 3 decisions
S += [P("3. Justificaci\u00f3n de Decisiones", h1),
      P("Servicios de AWS utilizados", h2)]
S.append(table([
    ["Servicio", "Por qu\u00e9 se eligi\u00f3", "Ventajas", "Desventajas"],
    ["EC2 (t3.small)", "El proyecto es una aplicaci\u00f3n Java en GlassFish, no un contenedor ni una funci\u00f3n. EC2 permite correr exactamente "
     "el mismo servidor y el mismo WAR que en local. Con 2 GB de RAM alcanza: GlassFish usa unos 500 MB (medido en el servidor) y MySQL y el sistema necesitan varios cientos m\u00e1s.",
     "Control total, mismo entorno que en desarrollo, costo fijo y predecible.",
     "Hay que administrar el sistema operativo y es una sola instancia en una sola zona."],
    ["EBS gp3", "Disco aparte para los datos de MySQL: se puede conservar o mover sin tocar el disco del sistema.",
     "3,000 IOPS incluidos, buen precio por GB.", "Atado a una zona de disponibilidad."],
    ["Elastic IP", "Mantiene la misma direcci\u00f3n al reconstruir o reiniciar el servidor. Sin ella, la URL cambia en cada arranque.",
     "URL estable, la prueba de p\u00e9rdida de servidor la conserv\u00f3.", "Tiene costo por hora aunque no se use."],
    ["S3", "Guarda los WAR y los respaldos fuera de la instancia, por lo que sobreviven si el servidor se pierde.",
     "Muy duradero, casi gratis a este tama\u00f1o, ciclo de vida para borrar respaldos de m\u00e1s de 30 d\u00edas.", "Solo es un almac\u00e9n de objetos."],
    ["SSM Parameter Store", "Contrase\u00f1as y secreto JWT cifrados y fuera del c\u00f3digo y del repositorio. Tambi\u00e9n guarda la versi\u00f3n vigente del WAR.",
     "Sin costo para par\u00e1metros est\u00e1ndar, se lee con el rol de la instancia (sin llaves en el servidor).", "Sin rotaci\u00f3n autom\u00e1tica de secretos."],
    ["CloudWatch", "Dos alarmas de estado con acci\u00f3n autom\u00e1tica: reiniciar si falla la instancia, recuperar si falla el host.",
     "Recuperaci\u00f3n sin intervenci\u00f3n humana.", "No detecta fallas de la aplicaci\u00f3n, solo de la m\u00e1quina."],
], [1.1 * inch, 2.35 * inch, 1.9 * inch, W - 5.35 * inch]))
S += [Spacer(1, 4), P("Decisiones de dise\u00f1o", h2)]
S.append(table([
    ["Decisi\u00f3n", "Alternativa considerada", "Raz\u00f3n"],
    ["MySQL en Docker dentro de la instancia", "Amazon RDS for MySQL",
     "RDS es m\u00e1s robusto (respaldos y parches administrados) pero costar\u00eda unos 70 USD m\u00e1s al a\u00f1o (escenario D, estimaci\u00f3n aproximada) y el laboratorio limita sus "
     "opciones. Con respaldos a S3 cada 6 horas y reconstrucci\u00f3n automatizada se obtuvo una recuperaci\u00f3n de unos 4.5 minutos. "
     "RDS queda como mejora (secci\u00f3n 6)."],
    ["Script de Python con boto3", "AWS CLI en .bat, CloudFormation, consola",
     "La materia exige crear la infraestructura con un script. Python permite l\u00f3gica (reutilizar recursos, reintentos, esperar a que la API "
     "responda) y se prob\u00f3 sin AWS real usando una simulaci\u00f3n (moto)."],
    ["Una sola instancia con nginx delante", "Balanceador de carga con varias instancias",
     "El balanceador tiene su propio costo fijo mensual y la aplicaci\u00f3n guarda estado en una sola base de datos. Para el alcance del proyecto "
     "se prefiri\u00f3 un dise\u00f1o simple y barato, y se prob\u00f3 que se reconstruye r\u00e1pido."],
    ["Despliegue por consulta (pull) cada 60 s", "Abrir el puerto 4848 de GlassFish o entrar por SSH",
     "El puerto de administraci\u00f3n nunca se expone. Actualizar y revertir son cambiar un par\u00e1metro. El desplegador rechaza archivos que "
     "no son WAR y restaura la versi\u00f3n anterior si GlassFish falla."],
    ["Secretos en SSM, no en el c\u00f3digo", "Archivo de configuraci\u00f3n en el repositorio",
     "Los secretos se generan al azar al crear la base, nunca se imprimen y el repositorio no los contiene."],
    ["Recursos con etiqueta Project=restaurant-review", "Borrar por nombre",
     "<font name='Courier'>destroy.py</font> solo toca lo etiquetado, as\u00ed que no afecta otros recursos de la cuenta del laboratorio."],
    ["Seguridad de red", "Todo abierto",
     "Solo el puerto 80 es p\u00fablico; el 22 solo desde la IP del administrador; MySQL solo en localhost; IMDSv2 obligatorio en la instancia; "
     "buckets sin acceso p\u00fablico."],
], [1.7 * inch, 1.6 * inch, W - 3.3 * inch]))
S.append(PageBreak())

# ------------------------------------------------------------------ 4 costs
def usd(x): return f"{x:,.2f}"
H = 8760
ec2 = 0.0209 * H; ebs = 0.08 * 18 * 12; ipv4 = 0.005 * H; cw = 0.10 * 2 * 12; s3 = 0.10
total = ec2 + ebs + ipv4 + cw + s3
hours_sched = 12 * 5 * 52
ec2_b = 0.0209 * hours_sched
total_b = ec2_b + ebs + ipv4 + cw + s3
egress = (150 - 100) * 0.09 * 12
S += [P("4. An\u00e1lisis de Costos", h1),
      P("Estimaci\u00f3n del costo de operar el sistema durante un a\u00f1o <b>fuera de la capa gratuita</b>, en us-east-1, bajo demanda, "
        "con 8,760 horas al a\u00f1o. En el laboratorio de AWS Academy el costo real es cero porque usa cr\u00e9ditos del curso; esta es la "
        "cuenta que corresponder\u00eda en una cuenta normal."),
      P("Precios unitarios usados", h2)]
S.append(table([
    ["Concepto", "Precio", "Fuente"],
    ["EC2 t3.small, Linux", "0.0209 USD por hora", "P\u00e1gina oficial de instancias T3"],
    ["EBS gp3", "0.08 USD por GB al mes", "P\u00e1gina oficial de precios de EBS"],
    ["Direcci\u00f3n IPv4 p\u00fablica (incluye Elastic IP)", "0.005 USD por hora, en uso o no", "Blog oficial de AWS"],
    ["Alarma de CloudWatch (resoluci\u00f3n est\u00e1ndar)", "0.10 USD al mes (10 alarmas gratis)", "P\u00e1gina oficial de CloudWatch"],
    ["S3 Standard", "0.023 USD por GB al mes; 0.005 USD por 1,000 PUT", "Art\u00edculo de terceros (la tabla oficial no se pudo leer)"],
    ["Transferencia de salida a Internet", "100 GB al mes gratis; luego 0.09 USD por GB", "Gratis: p\u00e1gina oficial. Precio por GB: art\u00edculo de terceros"],
    ["SSM Parameter Store (est\u00e1ndar)", "Sin costo adicional", "Documentaci\u00f3n de AWS (no verificado en esta sesi\u00f3n)"],
], [2.3 * inch, 2.25 * inch, W - 4.55 * inch]))
S += [Spacer(1, 6), P("Escenario A: como est\u00e1 desplegado (24 horas, 7 d\u00edas)", h2)]
S.append(table([
    ["Concepto", "C\u00e1lculo", "USD al a\u00f1o"],
    ["EC2 t3.small", "0.0209 x 8,760 h", usd(ec2)],
    ["EBS gp3 (8 GB sistema + 10 GB datos)", "0.08 x 18 GB x 12", usd(ebs)],
    ["Elastic IP (IPv4 p\u00fablica)", "0.005 x 8,760 h", usd(ipv4)],
    ["CloudWatch, 2 alarmas", "0.10 x 2 x 12 (sin descontar la capa gratuita)", usd(cw)],
    ["S3 (WAR, esquema y respaldos, menos de 1 GB)", "almacenamiento y solicitudes, aprox.", usd(s3)],
    ["SSM y transferencia (menos de 100 GB al mes)", "dentro de lo gratuito", "0.00"],
    ["<b>Total</b>", "", f"<b>{usd(total)}</b>"],
], [2.7 * inch, 2.7 * inch, W - 5.4 * inch]))
_sc = [Spacer(1, 6), P("Escenarios comparados", h2)]
_sc.append(table([
    ["Escenario", "Cambio respecto al A", "USD al a\u00f1o", "Comentario"],
    ["A. 24/7 (desplegado)", "-", usd(total), "Disponible siempre."],
    ["B. Apagado fuera de horario", f"Encendido 12 h al d\u00eda, 5 d\u00edas a la semana ({hours_sched:,} h al a\u00f1o). Se usa <font name='Courier'>deploy.py stop</font> y <font name='Courier'>start</font>.",
     usd(total_b), f"Ahorra {usd(total - total_b)} USD ({(total - total_b) / total * 100:.0f}%). El disco y la IP se siguen cobrando."],
    ["C. Con 150 GB de salida al mes", "50 GB por encima de lo gratuito cada mes", usd(total + egress), f"Suma {usd(egress)} USD. Es poco probable con este tr\u00e1fico."],
    ["D. Base de datos en RDS", "t3.micro para GlassFish y RDS for MySQL peque\u00f1o administrado", "aprox. 315", "Estimaci\u00f3n aproximada (el precio de RDS no se pudo verificar en la p\u00e1gina oficial). Mejor operaci\u00f3n, m\u00e1s caro."],
    ["E. t3.micro (1 GB)", "Mitad de memoria, 91 USD de EC2", "aprox. 155", "Descartado: GlassFish solo ya usa unos 500 MB; con MySQL y el sistema no quedar\u00eda margen en 1 GB."],
], [1.55 * inch, 2.3 * inch, 0.8 * inch, W - 4.65 * inch]))
S.append(KeepTogether(_sc))
S += [Spacer(1, 6), P("Lectura del an\u00e1lisis", h2)]
S += B([f"El costo est\u00e1 dominado por el c\u00f3mputo ({ec2 / total * 100:.0f}% del total). Por eso la medida m\u00e1s efectiva es apagar el servidor cuando no se usa, "
        "que adem\u00e1s es la decisi\u00f3n m\u00e1s sustentable: menos horas de c\u00f3mputo encendido para el mismo servicio.",
        f"La direcci\u00f3n IPv4 p\u00fablica cuesta {usd(ipv4)} USD al a\u00f1o, casi tanto como el almacenamiento y las alarmas juntos. Desde febrero de 2024 AWS la cobra aunque est\u00e9 en uso.",
        "Los precios cambian; las cifras son una estimaci\u00f3n con los valores publicados al redactar este documento y no incluyen impuestos."])
S.append(PageBreak())

# ------------------------------------------------------------------ 5 resilience
S += [P("5. Pruebas de Resiliencia", h1),
      P("El script <font name='Courier'>resilience_tests.py</font> provoca cada falla en el servidor real, mide cu\u00e1nto tarda en responder de nuevo "
        "y compara los datos antes y despu\u00e9s (7 restaurantes y 15 rese\u00f1as). Todas las pruebas pasaron.")]
res = [
    ["Falla provocada", "Qu\u00e9 se esperaba", "Qu\u00e9 pas\u00f3", "Tiempo"],
    ["Matar GlassFish (kill -9)", "systemd lo reinicia solo (Restart=always) y la app vuelve con los mismos datos.",
     "Respuestas 502 y 404 mientras reiniciaba, luego 200. Datos intactos.", "21.2 s"],
    ["Matar el proceso mysqld (kill -9)", "La API responde 500 sin caerse y Docker reinicia MySQL.",
     "Dos respuestas 500 limpias, luego 200. Datos intactos.", "4.5 s"],
    ["Carga: 300 peticiones con 20 usuarios y 60 logins simult\u00e1neos", "Ninguna petici\u00f3n falla; nginx limita la r\u00e1faga de logins.",
     "300 de 300 correctas (116 por segundo, mediana 163 ms, p95 192 ms). De 60 logins, 5 llegaron a la API (401) y 48 los bloque\u00f3 nginx. La API sigui\u00f3 en 200.", "sin ca\u00edda"],
    ["Publicar un archivo que no es un WAR", "Se rechaza sin tocar la versi\u00f3n en uso.", "Cero ca\u00eddas; el log del servidor muestra el rechazo.", "sin ca\u00edda"],
    ["Publicar un WAR con web.xml roto", "GlassFish no puede desplegarlo y se restaura la versi\u00f3n anterior.",
     "Una sola respuesta 404 durante la restauraci\u00f3n autom\u00e1tica, luego 200.", "6 s"],
    ["Terminar la instancia EC2 (se pierden servidor y discos)", "deploy.py la reconstruye, se reasocia la Elastic IP y se restauran los datos del \u00faltimo respaldo.",
     "Un comando reconstruy\u00f3 todo con la misma IP. Los datos restaurados coinciden (7 y 15).", "272.6 s (4.5 min)"],
]
S.append(table(res, [1.5 * inch, 1.8 * inch, W - 4.2 * inch, 0.9 * inch]))
S += [Spacer(1, 6), P("Observaciones", h2)]
S += B(["El tiempo de la \u00faltima prueba se mide desde que se pide terminar la instancia (unos 30 s) hasta que la API vuelve a responder 200.",
        "La prueba de p\u00e9rdida de servidor fuerza un respaldo justo antes de terminar la instancia. En operaci\u00f3n normal el respaldo es cada 6 horas, "
        "as\u00ed que ante una p\u00e9rdida total se podr\u00edan perder hasta 6 horas de datos (RPO de 6 horas). El intervalo se puede acortar.",
        "El primer intento de la prueba de MySQL us\u00f3 <i>docker kill</i> y MySQL no volvi\u00f3: Docker interpreta ese comando como una parada manual y no la reinicia aunque la pol\u00edtica sea "
        "<i>unless-stopped</i>. Se cambi\u00f3 la prueba para simular un fallo real (matar el proceso). Una parada manual con <i>docker stop</i> sigue sin reiniciarse a prop\u00f3sito.",
        "Las pruebas tambi\u00e9n encontraron defectos del propio despliegue, descritos en la gu\u00eda de la secci\u00f3n 1 (espera de MySQL, versi\u00f3n de Java, desplegador demasiado estricto)."])
S.append(PageBreak())

# ------------------------------------------------------------------ 6 limitations
S += [P("6. Limitaciones y trabajo futuro", h1)]
S.append(table([
    ["Limitaci\u00f3n", "Impacto", "Mejora posible"],
    ["Solo HTTP, sin HTTPS", "El token JWT y las contrase\u00f1as viajan sin cifrar entre el navegador y el servidor.",
     "Dominio propio y certificado (Let's Encrypt en nginx) o un balanceador con ACM. Requiere un dominio."],
    ["Una instancia en una zona", "Si falla la instancia o la zona hay una interrupci\u00f3n de unos 4.5 minutos (probado).", "Segunda instancia y balanceador, con su costo fijo."],
    ["Respaldos cada 6 horas", "RPO de hasta 6 horas.", "Respaldo m\u00e1s frecuente, o RDS con restauraci\u00f3n a un punto en el tiempo."],
    ["MySQL en la misma instancia", "Comparte memoria con GlassFish; los parches y respaldos son responsabilidad propia.", "RDS for MySQL (escenario D)."],
    ["Una conexi\u00f3n JDBC por petici\u00f3n", "Sin pool de conexiones; limita el rendimiento bajo mucha carga.", "Pool de conexiones administrado por GlassFish."],
    ["GET /reviews sin paginaci\u00f3n", "La respuesta crece con los datos.", "Paginaci\u00f3n con l\u00edmite y desplazamiento."],
    ["Alarmas solo del estado de la m\u00e1quina", "No detectan que la aplicaci\u00f3n responda mal.", "Endpoint de salud y alarma sobre \u00e9l."],
], [1.7 * inch, 2.7 * inch, W - 4.4 * inch]))
S += [Spacer(1, 12), P("7. Fuentes", h1)]
S += B(["Amazon EC2 T3 Instances (precios de t3.small): aws.amazon.com/ec2/instance-types/t3/",
        "Amazon EBS Pricing: aws.amazon.com/ebs/pricing",
        "New AWS Public IPv4 Address Charge: aws.amazon.com/blogs/aws/new-aws-public-ipv4-address-charge-public-ip-insights",
        "Amazon CloudWatch Pricing: aws.amazon.com/cloudwatch/pricing/",
        "Amazon EC2 On-Demand Pricing (100 GB mensuales de salida gratis): aws.amazon.com/ec2/pricing/on-demand/",
        "AWS Free Tier: aws.amazon.com/free/",
        "AWS S3 Pricing Explained (2026), Upstash (precios de S3 y de salida a Internet): upstash.com/blog/aws-s3-pricing-explained-2026",
        "Los precios de RDS (escenario D) son una estimaci\u00f3n aproximada; para el valor exacto usar la calculadora de AWS: calculator.aws"])

doc.build(S)
print("written", OUT, f"A={total:.2f} B={total_b:.2f} C={total + egress:.2f}")
