import pandas as pd
import requests
import time
from datetime import datetime
import os
import tempfile
import barcode
from barcode.writer import ImageWriter
import webbrowser
import streamlit as st
import json
import logging
import base64
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed
from Config.URLS import headersWMX
from collections import defaultdict

# Configuración de logging
logging.basicConfig(
    filename=r'C:\Users\bryan.marcial\OneDrive - GXO\Documents\PYTHON\Code\Local\Teo PutAway\hars\Logs\logs_proceso.log',
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def obtener_datos_estado(estado: str, headers: dict):
    base_url = "http://api-cqrs-wmxp001-wmx.am.gxo.com/queryservice/data/57585f4f52444552/4144445453/66616c7365/31/3330"
    columnas = ['ORDERKEY', 'SITEID', 'CLIENTID', 'EXTERNKEY', 'ORDERDATE', 
                'ORDERGROUP', 'PLANDELIVERYDATE', 'STATUS', 'STATUSTS', 'EDITWHO', 'TOTALORDERQTY']
    try:
        # Handle multiple statuses separated by |
        if '|' in estado:
            all_dfs = []
            for single_status in estado.split('|'):
                single_status = single_status.strip()
                log_msg = f"[LOG] PUT {base_url}\nHeaders: {headers}\nBody: {{'STATUS': '{single_status}'}}"
                print(log_msg)
                logging.info(log_msg)
                response = requests.put(
                    base_url,
                    json={"STATUS": single_status},
                    headers=headers,
                    timeout=10
                )
                log_msg = f"[LOG] Respuesta para {single_status}: {response.status_code} {response.text}"
                print(log_msg)
                logging.info(log_msg)
                if response.status_code == 200:
                    datos = response.json()
                    data_list = datos['Data'] if isinstance(datos['Data'], list) else [datos['Data']]
                    if data_list and data_list[0]:  # Check if data exists
                        df_single = pd.DataFrame(data_list)[columnas]
                        all_dfs.append(df_single)
            
            if all_dfs:
                # Combine all DataFrames
                df = pd.concat(all_dfs, ignore_index=True)
            else:
                df = pd.DataFrame(columns=columnas)
        else:
            # Single status (original logic)
            log_msg = f"[LOG] PUT {base_url}\nHeaders: {headers}\nBody: {{'STATUS': '{estado}'}}"
            print(log_msg)
            logging.info(log_msg)
            response = requests.put(
                base_url,
                json={"STATUS": estado},
                headers=headers,
                timeout=10
            )
            log_msg = f"[LOG] Respuesta: {response.status_code} {response.text}"
            print(log_msg)
            logging.info(log_msg)
            if response.status_code != 200:
                return pd.DataFrame()
            datos = response.json()
            data_list = datos['Data'] if isinstance(datos['Data'], list) else [datos['Data']]
            df = pd.DataFrame(data_list)[columnas]
        
        # Common processing for both single and multiple statuses
        if not df.empty:
            df['ORDERKEY'] = df['ORDERKEY'].astype(str)
            df['HEXORDER'] = df['ORDERKEY'].apply(lambda s: ''.join(f"{ord(c):02X}" for c in s))
        
        logging.info(f"[LOG] DataFrame generado: {len(df)} registros")
        print(f"DataFrame generado con {len(df)} registros")
        return df
    except Exception as e:
        logging.error(f"[ERROR] obtener_datos_estado: {e}")
        print(f"[ERROR] obtener_datos_estado: {e}")
        return pd.DataFrame()
#todo for Order Keys News
def cargar_ordenes(headers):
    logging.info("[LOG] Iniciando carga de órdenes...")
    print("[LOG] Iniciando carga de órdenes...")
    df_140 = obtener_datos_estado("101", headers)
    logging.info(f"[LOG] Órdenes cargadas: {df_140}")
    print("[LOG] Órdenes cargadas:")
    print(df_140)
    return df_140.copy()

def procesar_orden(hex_orderkey, headers):
    get_url = f"http://api-cqrs-wmxp001-wmx.am.gxo.com/queryservice/orderdtlbyorderkey/{hex_orderkey}"
    log_msg = f"[LOG] GET {get_url}\nHeaders: {headers}"
    print(log_msg)
    logging.info(log_msg)
    get_response = requests.get(get_url, headers=headers, timeout=30)
    log_msg = f"[LOG] Respuesta: {get_response.status_code} {get_response.text}"
    print(log_msg)
    logging.info(log_msg)
    if get_response.status_code == 200:
        try:
            df = pd.DataFrame(get_response.json())
            logging.info(f"[LOG] DataFrame procesado: {df}")
            return df
        except Exception as e:
            logging.error(f"[ERROR] procesar_orden: {e}")
            print(f"[ERROR] procesar_orden: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

# Función para generar código de barras y devolver la ruta de la imagen
def generar_barcode(valor, carpeta, nombre):
    code128 = barcode.get('code128', valor, writer=ImageWriter())
    ruta = os.path.join(carpeta, f"{nombre}.png")
    code128.save(ruta)
    return ruta

# Confirmación universal (solo consola)
def confirmar_accion(mensaje):
    resp = input(f"{mensaje} (s/n): ").strip().lower()
    return resp == 's'

# Paso 1: Allocate
def paso_allocate(orderkey_hex, headers):
    url = f"http://api-outbound-wmxp001-wmx.am.gxo.com/orderprocess/allocate/{orderkey_hex}/302e74386a7970786d6f6d6168"
    log_msg = f"[LOG] PUT {url}\nHeaders: {headers}\nBody: {{}}"
    print(log_msg)
    logging.info(log_msg)
    # En modo Streamlit, no se pregunta confirmación
    r = requests.put(url, json={}, headers=headers)
    log_msg = f"[LOG] Respuesta: {r.status_code} {r.text}"
    print(log_msg)
    logging.info(log_msg)
    return r.status_code == 200

# Paso 2: Release
def paso_release(orderkey_hex, headers):
    url = f"http://api-outbound-wmxp001-wmx.am.gxo.com/orderprocess/release/{orderkey_hex}"
    log_msg = f"[LOG] PUT {url}\nHeaders: {headers}\nBody: {{}}"
    print(log_msg)
    logging.info(log_msg)
    r = requests.put(url, json={}, headers=headers)
    log_msg = f"[LOG] Respuesta: {r.status_code} {r.text}"
    print(log_msg)
    logging.info(log_msg)
    return r.status_code == 200

# Paso 3: Consulta picks/cases
def paso_consulta(orderkey, headers, tipo):
    if tipo == 'case':
        url = "http://api-cqrs-wmxp001-wmx.am.gxo.com/queryservice/data/57585f4f524445525f43415345/4144445453/66616c7365/31/313030"
    else:
        url = "http://api-cqrs-wmxp001-wmx.am.gxo.com/queryservice/data/57585f4f524445525f5049434b/4144445453/66616c7365/31/313030"
    log_msg = f"[LOG] PUT {url}\nHeaders: {headers}\nBody: {{'ORDERKEY': '{orderkey}'}}"
    print(log_msg)
    logging.info(log_msg)
    r = requests.put(url, json={"ORDERKEY": orderkey}, headers=headers)
    log_msg = f"[LOG] Respuesta: {r.status_code} {r.text}"
    print(log_msg)
    logging.info(log_msg)
    if r.status_code == 200:
        try:
            data = r.json().get('Data', [])
            logging.info(f"[LOG] Datos consultados: {data}")
            return data
        except Exception as e:
            logging.error(f"[ERROR] paso_consulta: {e}")
            print(f"[ERROR] paso_consulta: {e}")
            return []
    return []

# Paso 4: Process
def paso_process(orderkey_hex, headers):
    url = f"http://api-outbound-wmxp001-wmx.am.gxo.com/orderprocess/process/{orderkey_hex}/302e6b327a6e6a6a73386e73"
    log_msg = f"[LOG] PUT {url}\nHeaders: {headers}\nBody: {{}}"
    print(log_msg)
    logging.info(log_msg)
    r = requests.put(url, json={}, headers=headers)
    log_msg = f"[LOG] Respuesta: {r.status_code} {r.text}"
    print(log_msg)
    logging.info(log_msg)
    return r.status_code == 200

# Paso 5: Print (genera HTML y abre navegador)
def paso_print(datos, carpeta, usuario):
    log_msg = f"[LOG] Generando HTML y códigos de barras para usuario: {usuario}"
    print(log_msg)
    logging.info(log_msg)
    filas = []
    def generar_fila(i_row):
        i, row = i_row
        try:
            caseid = str(row.get('CASEID', ''))
            orderkey = str(row.get('ORDERKEY', ''))
            sku = str(row.get('SKU', ''))
            fromloc = str(row.get('FROMLOC', ''))
            qty = str(row.get('QTY', row.get('PICKQTY', row.get('ORDERQTY', ''))))
            lot = str(row.get('LOT', ''))
            log_msg = f"[LOG] Generando códigos de barras para CASEID: {caseid}, ORDERKEY: {orderkey}, SKU: {sku}, FROMLOC: {fromloc}"
            logging.info(log_msg)
            return {
                'CASEID': caseid,
                'CASEID_BC': generar_barcode(caseid, carpeta, f"caseid_{i}"),
                'ORDERKEY': orderkey,
                'ORDERKEY_BC': generar_barcode(orderkey, carpeta, f"orderkey_{i}"),
                'SKU': sku,
                'SKU_BC': generar_barcode(sku, carpeta, f"sku_{i}"),
                'FROMLOC': fromloc,
                'FROMLOC_BC': generar_barcode(fromloc, carpeta, f"fromloc_{i}"),
                'QTY': qty,
                'LOT': lot
            }
        except Exception as e:
            logging.error(f"[ERROR] Error generando fila {i}: {e}")
            return None
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(generar_fila, enumerate(datos)))
    filas = [f for f in results if f]
    html = generar_html(filas, usuario)
    ruta_html = os.path.join(carpeta, "picking_list.html")
    try:
        with open(ruta_html, "w", encoding="utf-8") as f:
            f.write(html)
        log_msg = f"[LOG] HTML generado en: {ruta_html}"
        print(log_msg)
        logging.info(log_msg)
    except Exception as e:
        logging.error(f"[ERROR] Error guardando HTML: {e}")
    return ruta_html

def generar_html(filas, usuario):
    filas_html = ""
    for fila in filas:
        filas_html += f"""
        <tr>
            <td>{fila['CASEID']}</td>
            <td><img src='{fila['CASEID_BC']}' height='40'></td>
            <td>{fila['ORDERKEY']}</td>
            <td><img src='{fila['ORDERKEY_BC']}' height='40'></td>
            <td>{fila['SKU']}</td>
            <td><img src='{fila['SKU_BC']}' height='40'></td>
            <td>{fila['FROMLOC']}</td>
            <td><img src='{fila['FROMLOC_BC']}' height='40'></td>
            <td>{fila['QTY']}</td>
            <td>{fila['LOT']}</td>
        </tr>
        """
    return f"""
    <html><head><meta charset='utf-8'><title>Picking List</title></head><body>
    <h2>Picking List - Usuario: {usuario}</h2>
    <table border='1' cellpadding='4' cellspacing='0'>
        <tr><th>CASEID</th><th>CASEID BarCode</th><th>ORDERKEY</th><th>ORDERKEY BarCode</th><th>SKU</th><th>SKU BarCode</th><th>FROMLOC</th><th>FROMLOC BarCode</th><th>QTY</th><th>LOT</th></tr>
        {filas_html}
    </table>
    </body></html>
    """

# --- INICIO FUNCIONES DE ETIQUETA DE INVENTARIO ---
def filtrar_sku(datos):
    from collections import defaultdict
    from concurrent.futures import ThreadPoolExecutor
    locs_excluir = {"2-BLOCK", "PICKTO", "2-QUARANTINE", "LST"}
    skus = defaultdict(list)
    for d in datos:
        sku = d.get("SKU", "")
        if sku:
            skus[sku].append(d)
    def elegir_registro(registros):
        # Separar válidos y excluidos
        validos = [r for r in registros if not any(ex == r.get("LOC", r.get("FROMLOC", "")) for ex in locs_excluir)]
        excluidos = [r for r in registros if any(ex == r.get("LOC", r.get("FROMLOC", "")) for ex in locs_excluir)]
        if validos:
            return max(validos, key=lambda x: x.get("QTY", 0))
        elif excluidos:
            return max(excluidos, key=lambda x: x.get("QTY", 0))
        else:
            return registros[0]
    with ThreadPoolExecutor(max_workers=8) as executor:
        resultado = list(executor.map(elegir_registro, skus.values()))
    return resultado

def gen_barcode_etiqueta(valor, tipo):
    valor_str = str(valor)
    options = {"write_text": False, "module_width": 0.9, "module_height": 40, "quiet_zone": 0.0}
    code128 = barcode.get('code128', valor_str, writer=ImageWriter())
    buffer = BytesIO()
    code128.write(buffer, options)
    img_bytes = buffer.getvalue()
    base64_img = base64.b64encode(img_bytes).decode('utf-8')
    return f"data:image/png;base64,{base64_img}"

def generar_html_etiqueta(filas, orderkey, externalkey=None):
    try:
        with open('slogo.png', 'rb') as img_file:
            logo_base64 = base64.b64encode(img_file.read()).decode('utf-8')
        logo_src = f"data:image/png;base64,{logo_base64}"
    except Exception:
        logo_src = ''
    orderkey_bc = gen_barcode_etiqueta(orderkey, "ORDERKEY_MAIN")
    filas_primera = 8
    filas_otras = 10
    paginas = []
    if len(filas) <= filas_primera:
        paginas = [filas]
    else:
        paginas.append(filas[:filas_primera])
        for i in range(filas_primera, len(filas), filas_otras):
            paginas.append(filas[i:i+filas_otras])
    html = '''<html><head><meta charset='utf-8'>
    <link href="https://fonts.googleapis.com/css?family=Montserrat:400,700&display=swap" rel="stylesheet">
    <style>
    @page { size: Letter landscape; margin: 23px; }
    body { margin: 0; font-family: 'Montserrat', Arial, sans-serif; }
    .tabla-contenedor { width: 100%; box-sizing: border-box; }
    table { width: 100%; border-collapse: separate; border-spacing: 0; table-layout: fixed; page-break-inside: avoid; }
    th, td { border-right: 2.5px solid #fff; border-left: 2.5px solid #fff; }
    th { background: #444; color: #fff; font-size: 1.3em; padding: 2px 2px; letter-spacing: 0.5px; border-top: 2.5px solid #444; border-bottom: 2.5px solid #444; font-family: 'Montserrat', Arial, sans-serif; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    td { background: #fff; font-size: 1.1em; text-align: center; padding: 2px 2px 0px 2px; overflow-wrap: break-word; word-break: break-all; border-top: none; border-bottom: none; font-family: 'Montserrat', Arial, sans-serif; }
    tr.barcode-row td { border-bottom: 3.5px solid #222; background: #f4f8fb; padding-top: 0px; padding-bottom: 10px; }
    img.barcode { width: 100%; max-width: 140px; height: 40px; object-fit: contain; display: block; margin: 0 auto 0 auto; }
    .header {display:flex;justify-content:space-between;align-items:center;margin-bottom:2px;max-height:70px;}
    .logo {height:40px;}
    .titulo {font-size:1.5em;font-weight:bold;letter-spacing:2px;font-family: 'Montserrat', Arial, sans-serif;}
    .orderkey-box {text-align:left;}
    .orderkey-text {font-size:1.3em;font-weight:bold;letter-spacing:1px;font-family: 'Montserrat', Arial, sans-serif;}
    .orderkey-barcode {height:40px;}
    .page-break { page-break-after: always; }
    .tabla-pagina { break-inside: avoid; page-break-inside: avoid; margin-bottom: 30px; }
    tr, td, th { break-inside: avoid; page-break-inside: avoid; }
    @media print {
      body {margin:0;}
      .page-footer {position:fixed;bottom:0;left:0;width:100vw;text-align:center;font-size:1.1em;}
    }
    </style></head><body>'''
    html += "<div class='header'>"
    html += f"<div class='orderkey-box'><div class='orderkey-text'>{orderkey}</div><img src='{orderkey_bc}' class='orderkey-barcode'></div>"
    if externalkey:
        html += f"<div class='titulo'>Picking List / {externalkey}</div>"
    else:
        html += "<div class='titulo'>Picking List</div>"
    html += "<img src='data:image/png;base64,iVBORw0KGCYII=' class='logo'>"
    html += "</div>"
    html += "<div class='tabla-contenedor'>"
    for num_pagina, pagina in enumerate(paginas, 1):
        html += f"<table class='tabla-pagina'><tr><th>SKU</th><th>LOT</th><th>LOC</th><th>QTY</th></tr>"
        for f in pagina:
            sku_bc = gen_barcode_etiqueta(f.get("SKU", ""), "SKU")
            lot_bc = gen_barcode_etiqueta(f.get("LOT", ""), "LOT")
            loc_bc = gen_barcode_etiqueta(f.get("FROMLOC", f.get("LOC", "")), "LOC")
            qty_bc = gen_barcode_etiqueta(f.get("QTY", ""), "QTY")
            html += f"<tr class='data-row'>"
            html += f"<td style='font-size:1.3em;padding:2px 2px 0px 2px;border:none;'>{f.get('SKU','')}</td>"
            html += f"<td style='font-size:1.5em;padding:2px 2px 0px 2px;border:none;'>{f.get('LOT','')}</td>"
            html += f"<td style='font-size:1.5em;padding:2px 2px 0px 2px;border:none;'>{f.get('FROMLOC', f.get('LOC',''))}</td>"
            html += f"<td style='font-size:1.5em;padding:2px 2px 0px 2px;border:none;'>{f.get('QTY','')}</td>"
            html += "</tr>"
            html += f"<tr class='barcode-row'>"
            html += f"<td style='padding-top:0px;padding-bottom:6px;border-top:0;border-bottom:3.5px solid #222;'><img src='{sku_bc}' class='barcode'></td>"
            html += f"<td style='padding-top:0px;padding-bottom:6px;border-top:0;border-bottom:3.5px solid #222;'><img src='{lot_bc}' class='barcode'></td>"
            html += f"<td style='padding-top:0px;padding-bottom:6px;border-top:0;border-bottom:3.5px solid #222;'><img src='{loc_bc}' class='barcode'></td>"
            html += f"<td style='padding-top:0px;padding-bottom:6px;border-top:0;border-bottom:3.5px solid #222;'><img src='{qty_bc}' class='barcode'></td>"
            html += "</tr>"
        html += f"</table>"
        if num_pagina < len(paginas):
            html += "<div class='page-break'></div>"
    html += "</div>"
    html += "</body></html>"
    return html

# --- INICIO FLUJO DE DATOS PARA ETIQUETA DE INVENTARIO ---
def obtener_datos_etiqueta(orderkey_hex, headers, externalkey=None):
    url_detalle = f"http://api-cqrs-wmxp001-wmx.am.gxo.com/queryservice/orderdtlbyorderkey/{orderkey_hex}"
    try:
        r = requests.get(url_detalle, headers=headers, timeout=50)
        if r.status_code != 200:
            return []
        detalles = r.json()
        if not isinstance(detalles, list):
            detalles = [detalles]
        resultado = []
        def fetch_inv(d):
            sku = d.get("SKU", "")
            qty_requerida = d.get("ORDERQTY", 0)
            if not sku or not qty_requerida:
                return []
            url_inv = "http://api-cqrs-wmxp001-wmx.am.gxo.com/queryservice/data/434f5245494e565f494e56454e544f52595f5657/4c4f5441445431/74727565/31/31303030"
            payload = {"SKU": sku, "QTY": ">0"}
            try:
                r_inv = requests.put(url_inv, json=payload, headers=headers, timeout=15)
                if r_inv.status_code != 200:
                    return []
                data_inv = r_inv.json().get("Data", [])
                if not isinstance(data_inv, list):
                    data_inv = [data_inv]
                registros = []
                for inv in data_inv:
                    registros.append({
                        "ORDERKEY": d.get("ORDERKEY", ""),
                        "SKU": sku,
                        "LOT": inv.get("LOT", ""),
                        "LOC": inv.get("LOC", ""),
                        "LPN": inv.get("LPN", ""),
                        "QTY": inv.get("QTY", 0),
                        "EXTERNALKEY": externalkey
                    })
                return registros
            except Exception as e:
                print(f"[ERROR] fetch_inv: {e}")
                return []
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(fetch_inv, detalles))
        # Flatten results
        resultado = [item for sublist in results for item in sublist if item]
        return resultado
    except Exception as e:
        print(f"[ERROR] obtener_datos_etiqueta: {e}")
        return []
# --- FIN FLUJO DE DATOS PARA ETIQUETA DE INVENTARIO ---

st.set_page_config(page_title="Picking List WMX", layout="wide")

# Add logo if available
try:
    st.image("logo.png", width=200)
except:
    pass  # Logo not found, continue without it

st.title("Picking List WMX")

# --- NUEVO: Pestañas para impresión y reimpresión ---
tab1, tab2, tab3, tab_debug = st.tabs(["Impresión", "Reimpresión", "Buscar por OrderKey", "Debug Etiqueta"])

with tab1:
    if 'usuario' not in st.session_state:
        st.session_state['usuario'] = ''
    if 'ordenes' not in st.session_state:
        st.session_state['ordenes'] = None
    if 'headersWMX' not in st.session_state:
        st.session_state['headersWMX'] = None
    if 'seleccion_idx' not in st.session_state:
        st.session_state['seleccion_idx'] = None
    if 'status' not in st.session_state:
        st.session_state['status'] = ''

    lista_usuarios = [
        "america.torres",
        "jose.centeno002",
        "guillermo.betanzos",
        "edgar.carabeo"
    ]

    usuario = st.selectbox("Usuario WMX", options=lista_usuarios, index=lista_usuarios.index(st.session_state['usuario']) if st.session_state['usuario'] in lista_usuarios else 0)
    st.session_state['usuario'] = usuario

    headersWMX = headersWMX.copy()
    headersWMX["xposc-userid"] = usuario
    st.session_state['headersWMX'] = headersWMX

    if 'last_reload' not in st.session_state:
        st.session_state['last_reload'] = time.time()
    if time.time() - st.session_state['last_reload'] > 120:
        st.session_state['last_reload'] = time.time()
        st.session_state['ordenes'] = cargar_ordenes(headersWMX)
        st.rerun()

    if st.button("Cargar órdenes") or (st.session_state['ordenes'] is not None and st.session_state['usuario'] != ""):
        st.session_state['ordenes'] = cargar_ordenes(headersWMX)
        if st.session_state['ordenes'].empty:
            st.error("No se encontraron órdenes")
        else:
            st.success(f"Órdenes encontradas: {len(st.session_state['ordenes'])}")

    if st.session_state['ordenes'] is not None and not st.session_state['ordenes'].empty:
        ordenes = st.session_state['ordenes']
        st.subheader("Órdenes disponibles")
        st.dataframe(ordenes, use_container_width=True)
        opciones = [f"{row['EXTERNKEY']} ({row['ORDERKEY']})" for _, row in ordenes.iterrows()]
        idx = st.selectbox("Selecciona una orden para procesar", options=list(range(len(opciones))), format_func=lambda i: opciones[i])
        st.session_state['seleccion_idx'] = idx
        row = ordenes.iloc[idx]
        orderkey = row['ORDERKEY']
        orderkey_hex = row['HEXORDER']
        usuario = row.get('EDITWHO', usuario)
        if 'confirmar' not in st.session_state:
            st.session_state['confirmar'] = False

        col1, col2, col3 = st.columns([2,2,1])
        with col3:
            if not usuario:
                st.warning("Selecciona un usuario WMX para continuar.")
            else:
                if st.button("Generar y descargar Picking List", key="generar_descargar"):
                    logging.info(f"[LOG] Iniciando generación y descarga de Picking List para {orderkey} / {row['EXTERNKEY']}")
                    datos_etiqueta = obtener_datos_etiqueta(orderkey_hex, st.session_state['headersWMX'], row['EXTERNKEY'])
                    if not datos_etiqueta:
                        logging.warning(f"[LOG] No se encontraron datos para la etiqueta {orderkey}")
                        st.error("No se encontraron datos para la etiqueta")
                        st.stop()
                    filtrados = filtrar_sku(datos_etiqueta)
                    def fila_html(f):
                        try:
                            return f
                        except Exception as e:
                            logging.error(f"[ERROR] Error generando fila HTML: {e}")
                            return None
                    with ThreadPoolExecutor(max_workers=8) as executor:
                        filas_finales = list(executor.map(fila_html, filtrados))
                    filas_finales = [f for f in filas_finales if f]
                    html_etiqueta = generar_html_etiqueta(filas_finales, orderkey, row['EXTERNKEY'])
                    logging.info(f"[LOG] Etiqueta generada correctamente para {orderkey}")
                    st.download_button(f"Descargar Picking List {orderkey}", data=html_etiqueta, file_name=f"PickingList_{orderkey}.html", mime="text/html")

        if st.button("Procesar orden seleccionada"):
            st.session_state['confirmar'] = True
        if st.session_state['confirmar']:
            st.warning(f"¿Seguro que deseas procesar la orden {row['EXTERNKEY']} ({orderkey})?")
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("Sí, procesar ahora"):
                    st.session_state['confirmar'] = False
                    st.session_state['status'] = "Ejecutando ALLOCATE..."
                    if not paso_allocate(orderkey_hex, st.session_state['headersWMX']):
                        st.error("Error en ALLOCATE")
                        st.stop()
                    st.session_state['status'] = "Ejecutando RELEASE..."
                    if not paso_release(orderkey_hex, st.session_state['headersWMX']):
                        st.error("Error en RELEASE")
                        st.stop()
                    st.session_state['status'] = "Ejecutando PROCESS..."
                    if not paso_process(orderkey_hex, st.session_state['headersWMX']):
                        st.error("Error en PROCESS")
                        st.stop()
                    st.session_state['status'] = "Generando Picking List..."
                    datos_etiqueta = obtener_datos_etiqueta(orderkey_hex, st.session_state['headersWMX'], row['EXTERNKEY'])
                    if not datos_etiqueta:
                        st.error("No se encontraron datos para la etiqueta")
                        st.stop()
                    filtrados = filtrar_sku(datos_etiqueta)
                    html_etiqueta = generar_html_etiqueta(filtrados, orderkey, row['EXTERNKEY'])
                    st.success("¡Proceso completado! ya puedes descargar el Picking List.")
                    st.download_button(
                        label=f"Descargar Picking List {orderkey}",
                        data=html_etiqueta,
                        file_name=f"PickingList_{orderkey}.html",
                        mime="text/html"
                    )
                    st.session_state['status'] = "¡Completado!"
            with col2:
                if st.button("Cancelar"):
                    st.session_state['confirmar'] = False
            with col3:
                if st.button("Generar etiqueta de inventario"):
                    logging.info(f"[LOG] Iniciando generación de etiqueta de inventario para {orderkey} / {row['EXTERNKEY']}")
                    datos_etiqueta = obtener_datos_etiqueta(orderkey_hex, st.session_state['headersWMX'], row['EXTERNKEY'])
                    if not datos_etiqueta:
                        logging.warning(f"[LOG] No se encontraron datos para la etiqueta {orderkey}")
                        st.error("No se encontraron datos para la etiqueta")
                        st.stop()
                    filtrados = filtrar_sku(datos_etiqueta)
                    with ThreadPoolExecutor(max_workers=8) as executor:
                        filas_finales = list(executor.map(lambda f: f, filtrados))
                    filas_finales = [f for f in filas_finales if f]
                    html_etiqueta = generar_html_etiqueta(filas_finales, orderkey, row['EXTERNKEY'])
                    logging.info(f"[LOG] Etiqueta de inventario generada correctamente para {orderkey}")
                    st.download_button("Descargar Picking List", data=html_etiqueta, file_name="PickingList.html", mime="text/html")
    st.write(st.session_state['status'])

# --- NUEVO: Pestaña de Reimpresión ---
with tab2:
    st.subheader("Órdenes ya procesadas (para reimpresión)")
    df_reimp = obtener_datos_estado("130|150|145", headersWMX)
    if df_reimp.empty:
        st.info("No hay órdenes procesadas para reimprimir.")
    else:
        st.dataframe(df_reimp, use_container_width=True)
        opciones_reimp = [f"EXTERNALKEY {row['EXTERNKEY']} / / / ORDERKEY ({row['ORDERKEY']})" for _, row in df_reimp.iterrows()]
        idx_reimp = st.selectbox("Selecciona una orden para reimprimir", options=list(range(len(opciones_reimp))), format_func=lambda i: opciones_reimp[i], key="reimp_idx")
        row_reimp = df_reimp.iloc[idx_reimp]
        orderkey_reimp = row_reimp['ORDERKEY']
        orderkey_hex_reimp = row_reimp['HEXORDER']
        usuario_reimp = row_reimp.get('EDITWHO', '')
        st.write(f"Seleccionada: {row_reimp['EXTERNKEY']} ({orderkey_reimp})")
        # Consultas y respuestas
        st.markdown("### Respuestas de consultas para esta orden:")
        # Consulta detalle
        detalle = procesar_orden(orderkey_hex_reimp, headersWMX)
        st.write("Detalle de la orden:")
        st.dataframe(detalle, use_container_width=True)
        # Consulta picks
        picks = paso_consulta(orderkey_reimp, headersWMX, tipo='pick')
        st.write("Picks:")
        st.write(picks)
        # Consulta cases
        cases = paso_consulta(orderkey_reimp, headersWMX, tipo='case')
        st.write("Cases:")
        st.write(cases)
        # Botón de reimpresión
        if st.button("Reimprimir Picking List"):
            datos_etiqueta = obtener_datos_etiqueta(orderkey_hex_reimp, headersWMX, row_reimp['EXTERNKEY'])
            if not datos_etiqueta:
                st.error("No se encontraron datos para la etiqueta")
            else:
                filtrados = filtrar_sku(datos_etiqueta)
                html_etiqueta = generar_html_etiqueta(filtrados, orderkey_reimp, row_reimp['EXTERNKEY'])
                st.download_button(f"Descargar Picking List {orderkey_reimp}", data=html_etiqueta, file_name=f"PickingList_{orderkey_reimp}_reimp.html", mime="text/html")

with tab3:
    st.subheader("Buscar por OrderKey específico")
    orderkey_buscar = st.text_input("Introduce el OrderKey a buscar", "")
    if orderkey_buscar:
        # Consulta por OrderKey (no por status)
        try:
            base_url = "http://api-cqrs-wmxp001-wmx.am.gxo.com/queryservice/data/57585f4f52444552/4144445453/66616c7365/31/3330"
            columnas = ['ORDERKEY', 'SITEID', 'CLIENTID', 'EXTERNKEY', 'ORDERDATE', 'ORDERGROUP', 'PLANDELIVERYDATE', 'STATUS', 'STATUSTS', 'EDITWHO', 'TOTALORDERQTY']
            log_msg = f"[LOG] PUT {base_url} buscando ORDERKEY: {orderkey_buscar}"
            print(log_msg)
            logging.info(log_msg)
            response = requests.put(
                base_url,
                json={"ORDERKEY": orderkey_buscar},
                headers=headersWMX,
                timeout=100
            )
            log_msg = f"[LOG] Respuesta: {response.status_code} {response.text}"
            print(log_msg)
            logging.info(log_msg)
            if response.status_code == 200:
                datos = response.json()
                data_list = datos['Data'] if isinstance(datos['Data'], list) else [datos['Data']]
                if data_list and data_list[0].get('ORDERKEY'):
                    df_okey = pd.DataFrame(data_list)[columnas]
                    df_okey['ORDERKEY'] = df_okey['ORDERKEY'].astype(str)
                    df_okey['HEXORDER'] = df_okey['ORDERKEY'].apply(lambda s: ''.join(f"{ord(c):02X}" for c in s))
                    st.dataframe(df_okey, use_container_width=True)
                    row_okey = df_okey.iloc[0]
                    orderkey = row_okey['ORDERKEY']
                    orderkey_hex = row_okey['HEXORDER']
                    usuario = row_okey.get('EDITWHO', '')
                    st.write(f"Seleccionada: {row_okey['EXTERNKEY']} ({orderkey})")
                    st.markdown("### Respuestas de consultas para este OrderKey:")
                    detalle = procesar_orden(orderkey_hex, headersWMX)
                    st.write("Detalle de la orden:")
                    st.dataframe(detalle, use_container_width=True)
                    picks = paso_consulta(orderkey, headersWMX, tipo='pick')
                    #st.write("Picks:")
                    #st.write(picks)
                    cases = paso_consulta(orderkey, headersWMX, tipo='case')
                    #st.write("Cases:")
                    #st.write(cases)
                    if st.button("Reimprimir Picking List", key="reimp_orderkey"):
                        datos_etiqueta = obtener_datos_etiqueta(orderkey_hex, headersWMX, row_okey['EXTERNKEY'])
                        if not datos_etiqueta:
                            st.error("No se encontraron datos para la etiqueta")
                        else:
                            filtrados = filtrar_sku(datos_etiqueta)
                            html_etiqueta = generar_html_etiqueta(filtrados, orderkey, row_okey['EXTERNKEY'])
                            st.download_button(f"Descargar Picking List {orderkey}", data=html_etiqueta, file_name=f"PickingList_{orderkey}_busqueda.html", mime="text/html")
                else:
                    st.info("No se encontró ninguna orden con ese OrderKey.")
            else:
                st.error("Error en la consulta. Verifica el OrderKey.")
        except Exception as e:
            st.error(f"Error en la consulta: {e}")

with tab_debug:
    st.subheader("Debug de generación de etiqueta (por OrderKey)")
    orderkey_debug = st.text_input("OrderKey para debug", "")
    if orderkey_debug:
        try:
            base_url = "http://api-cqrs-wmxp001-wmx.am.gxo.com/queryservice/data/57585f4f52444552/4144445453/66616c7365/31/3330"
            columnas = ['ORDERKEY', 'SITEID', 'CLIENTID', 'EXTERNKEY', 'ORDERDATE', 'ORDERGROUP', 'PLANDELIVERYDATE', 'STATUS', 'STATUSTS', 'EDITWHO', 'TOTALORDERQTY']
            log_msg = f"[DEBUG] PUT {base_url} buscando ORDERKEY: {orderkey_debug}"
            print(log_msg)
            logging.info(log_msg)
            response = requests.put(
                base_url,
                json={"ORDERKEY": orderkey_debug},
                headers=headersWMX,
                timeout=100
            )
            log_msg = f"[DEBUG] Respuesta: {response.status_code} {response.text}"
            print(log_msg)
            logging.info(log_msg)
            if response.status_code == 200:
                datos = response.json()
                data_list = datos['Data'] if isinstance(datos['Data'], list) else [datos['Data']]
                if data_list and data_list[0].get('ORDERKEY'):
                    df_okey = pd.DataFrame(data_list)[columnas]
                    df_okey['ORDERKEY'] = df_okey['ORDERKEY'].astype(str)
                    df_okey['HEXORDER'] = df_okey['ORDERKEY'].apply(lambda s: ''.join(f"{ord(c):02X}" for c in s))
                    st.dataframe(df_okey, use_container_width=True)
                    row_okey = df_okey.iloc[0]
                    orderkey = row_okey['ORDERKEY']
                    orderkey_hex = row_okey['HEXORDER']
                    usuario = row_okey.get('EDITWHO', '')
                    st.write(f"Seleccionada: {row_okey['EXTERNKEY']} ({orderkey})")
                    st.markdown("### 1. Datos crudos de la orden:")
                    detalle = procesar_orden(orderkey_hex, headersWMX)
                    st.dataframe(detalle, use_container_width=True)
                    st.markdown("### 2. Datos de inventario obtenidos para cada SKU:")
                    datos_etiqueta = obtener_datos_etiqueta(orderkey_hex, headersWMX, row_okey['EXTERNKEY'])
                    st.write(datos_etiqueta)
                    st.markdown(f"Total registros inventario: {len(datos_etiqueta)}")
                    st.markdown("### 3. Datos después de filtrar_sku:")
                    filtrados = filtrar_sku(datos_etiqueta)
                    st.write(filtrados)
                    st.markdown(f"Total registros filtrados: {len(filtrados)}")
                    st.markdown("### 4. HTML generado (preview):")
                    html_etiqueta = generar_html_etiqueta(filtrados, orderkey, row_okey['EXTERNKEY'])
                    st.download_button(f"Descargar HTML Debug {orderkey}", data=html_etiqueta, file_name=f"PickingList_{orderkey}_debug.html", mime="text/html")
                    st.code(html_etiqueta[:2000] + ("..." if len(html_etiqueta) > 2000 else ""), language="html")
                else:
                    st.info("No se encontró ninguna orden con ese OrderKey.")
            else:
                st.error("Error en la consulta. Verifica el OrderKey.")
        except Exception as e:
            st.error(f"Error en la consulta: {e}")


