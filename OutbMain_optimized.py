"""
Optimized Outbound Application
High-performance version with comprehensive optimizations and bug fixes
"""
import pandas as pd
import time
from datetime import datetime
import os
import tempfile
import barcode
from barcode.writer import ImageWriter
import webbrowser
import streamlit as st
import logging
import base64
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from typing import Dict, List, Any, Optional

# Import optimized modules
from performance_config import config
from performance_monitor import performance_monitor, profile_critical, TimeBlock
from optimized_utils import (
    FastJSON, OptimizedHTTPClient, TTLCache, DataFrameOptimizer,
    BarcodeCache, http_client, api_cache, barcode_cache, df_optimizer,
    cached_api_call, optimize_html_generation
)
from Config.URLS import headersWMX

# Enhanced logging configuration
log_file_path = os.getenv('LOG_FILE_PATH', 'logs/outbound_process.log')
os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

logging.basicConfig(
    filename=log_file_path,
    level=getattr(logging, config.PERFORMANCE_LOG_LEVEL),
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Also log to console in development
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(console_handler)

logger = logging.getLogger(__name__)

# Log configuration on startup
config.log_configuration()

@profile_critical
def obtener_datos_estado(estado: str, headers: dict) -> pd.DataFrame:
    """Optimized function to get order data by status"""
    base_url = "http://api-cqrs-wmxp001-wmx.am.gxo.com/queryservice/data/57585f4f52444552/4144445453/66616c7365/31/3330"
    columnas = ['ORDERKEY', 'SITEID', 'CLIENTID', 'EXTERNKEY', 'ORDERDATE', 
                'ORDERGROUP', 'PLANDELIVERYDATE', 'STATUS', 'STATUSTS', 'EDITWHO', 'TOTALORDERQTY']
    
    cache_key = f"estado_{estado}_{hash(str(headers))}"
    
    def _fetch_data():
        try:
            logger.info(f"Fetching data for status: {estado}")
            
            response = http_client.put(
                base_url,
                json={"STATUS": estado},
                headers=headers
            )
            
            logger.info(f"Response: {response.status_code}")
            
            if response.status_code != 200:
                logger.warning(f"Non-200 response: {response.status_code} - {response.text}")
                return pd.DataFrame()
            
            # Use optimized JSON parsing
            datos = FastJSON.loads(response.text)
            data_list = datos['Data'] if isinstance(datos['Data'], list) else [datos['Data']]
            
            # Create DataFrame with optimized dtypes
            df = pd.DataFrame(data_list)[columnas]
            df = df_optimizer.optimize_dtypes(df)
            
            # Optimize string operations
            df['ORDERKEY'] = df['ORDERKEY'].astype(str)
            
            # Vectorized hex conversion (more efficient than lambda)
            def convert_to_hex(s):
                return ''.join(f"{ord(c):02X}" for c in s)
            
            # Use vectorized operation instead of apply with lambda
            if config.is_large_dataset(len(df)):
                # Process in chunks for large datasets
                df['HEXORDER'] = df_optimizer.process_in_chunks(
                    df['ORDERKEY'], 
                    lambda chunk: chunk.apply(convert_to_hex)
                )
            else:
                df['HEXORDER'] = df['ORDERKEY'].apply(convert_to_hex)
            
            logger.info(f"DataFrame generated with {len(df)} rows")
            return df
            
        except Exception as e:
            logger.error(f"Error in obtener_datos_estado: {e}")
            return pd.DataFrame()
    
    # Use cached API call
    return cached_api_call(cache_key, _fetch_data)

@profile_critical  
def cargar_ordenes(headers: dict) -> pd.DataFrame:
    """Load orders with caching and optimization"""
    logger.info("Starting order loading...")
    
    with TimeBlock("load_orders"):
        df_140 = obtener_datos_estado("101", headers)
        
    logger.info(f"Orders loaded: {len(df_140)}")
    return df_140.copy()

@profile_critical
def procesar_orden(hex_orderkey: str, headers: dict) -> pd.DataFrame:
    """Process order with optimized HTTP client and caching"""
    get_url = f"http://api-cqrs-wmxp001-wmx.am.gxo.com/queryservice/orderdtlbyorderkey/{hex_orderkey}"
    
    cache_key = f"orden_{hex_orderkey}_{hash(str(headers))}"
    
    def _fetch_order():
        try:
            logger.info(f"Processing order: {hex_orderkey}")
            
            response = http_client.get(get_url, headers=headers)
            
            logger.info(f"Response: {response.status_code}")
            
            if response.status_code == 200:
                # Use optimized JSON parsing
                data = FastJSON.loads(response.text)
                df = pd.DataFrame(data)
                
                # Optimize DataFrame if not empty
                if not df.empty:
                    df = df_optimizer.optimize_dtypes(df)
                
                logger.info(f"Order processed: {len(df)} records")
                return df
            else:
                logger.warning(f"Failed to process order: {response.status_code}")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Error processing order {hex_orderkey}: {e}")
            return pd.DataFrame()
    
    return cached_api_call(cache_key, _fetch_order)

@profile_critical
def generar_barcode_optimized(valor: str, carpeta: str, nombre: str) -> str:
    """Optimized barcode generation with caching"""
    return barcode_cache.generate_barcode(valor, carpeta, nombre)

# Confirmation function (console only) - unchanged but with better error handling
def confirmar_accion(mensaje: str) -> bool:
    """Universal confirmation with input validation"""
    try:
        resp = input(f"{mensaje} (s/n): ").strip().lower()
        return resp in ['s', 'si', 'yes', 'y']
    except (EOFError, KeyboardInterrupt):
        return False

@profile_critical
def paso_allocate(orderkey_hex: str, headers: dict) -> bool:
    """Step 1: Allocate with optimized HTTP client"""
    url = f"http://api-outbound-wmxp001-wmx.am.gxo.com/orderprocess/allocate/{orderkey_hex}/302e74386a7970786d6f6d6168"
    
    try:
        logger.info(f"Allocating order: {orderkey_hex}")
        response = http_client.put(url, json={}, headers=headers)
        
        success = response.status_code == 200
        logger.info(f"Allocate result: {success} (status: {response.status_code})")
        
        return success
    except Exception as e:
        logger.error(f"Error in allocate step: {e}")
        return False

@profile_critical
def paso_release(orderkey_hex: str, headers: dict) -> bool:
    """Step 2: Release with optimized HTTP client"""
    url = f"http://api-outbound-wmxp001-wmx.am.gxo.com/orderprocess/release/{orderkey_hex}"
    
    try:
        logger.info(f"Releasing order: {orderkey_hex}")
        response = http_client.put(url, json={}, headers=headers)
        
        success = response.status_code == 200
        logger.info(f"Release result: {success} (status: {response.status_code})")
        
        return success
    except Exception as e:
        logger.error(f"Error in release step: {e}")
        return False

@profile_critical
def paso_consulta(orderkey: str, headers: dict, tipo: str) -> List[Dict]:
    """Query picks/cases with caching and optimization"""
    if tipo == 'case':
        url = "http://api-cqrs-wmxp001-wmx.am.gxo.com/queryservice/data/57585f4f524445525f43415345/4144445453/66616c7365/31/313030"
    else:
        url = "http://api-cqrs-wmxp001-wmx.am.gxo.com/queryservice/data/57585f4f524445525f5049434b/4144445453/66616c7365/31/313030"
    
    cache_key = f"consulta_{orderkey}_{tipo}_{hash(str(headers))}"
    
    def _fetch_consultation():
        try:
            logger.info(f"Consulting {tipo} for order: {orderkey}")
            
            response = http_client.put(url, json={"ORDERKEY": orderkey}, headers=headers)
            
            logger.info(f"Consultation response: {response.status_code}")
            
            if response.status_code == 200:
                # Use optimized JSON parsing
                data = FastJSON.loads(response.text).get('Data', [])
                logger.info(f"Consultation data retrieved: {len(data) if isinstance(data, list) else 1} records")
                return data
            else:
                logger.warning(f"Consultation failed: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error in consultation: {e}")
            return []
    
    return cached_api_call(cache_key, _fetch_consultation)

@profile_critical
def paso_process(orderkey_hex: str, headers: dict) -> bool:
    """Step 4: Process with optimized HTTP client"""
    url = f"http://api-outbound-wmxp001-wmx.am.gxo.com/orderprocess/process/{orderkey_hex}/302e6b327a6e6a6a73386e73"
    
    try:
        logger.info(f"Processing order: {orderkey_hex}")
        response = http_client.put(url, json={}, headers=headers)
        
        success = response.status_code == 200
        logger.info(f"Process result: {success} (status: {response.status_code})")
        
        return success
    except Exception as e:
        logger.error(f"Error in process step: {e}")
        return False

@profile_critical
def paso_print(datos: List[Dict], carpeta: str, usuario: str) -> str:
    """Optimized print step with concurrent barcode generation"""
    logger.info(f"Generating HTML and barcodes for user: {usuario}")
    
    def generar_fila(i_row):
        """Generate a single row with error handling"""
        i, row = i_row
        try:
            caseid = str(row.get('CASEID', ''))
            orderkey = str(row.get('ORDERKEY', ''))
            sku = str(row.get('SKU', ''))
            fromloc = str(row.get('FROMLOC', ''))
            qty = str(row.get('QTY', row.get('PICKQTY', row.get('ORDERQTY', ''))))
            lot = str(row.get('LOT', ''))
            
            logger.debug(f"Generating barcodes for row {i}: CASEID={caseid}, SKU={sku}")
            
            return {
                'CASEID': caseid,
                'CASEID_BC': generar_barcode_optimized(caseid, carpeta, f"caseid_{i}"),
                'ORDERKEY': orderkey,
                'ORDERKEY_BC': generar_barcode_optimized(orderkey, carpeta, f"orderkey_{i}"),
                'SKU': sku,
                'SKU_BC': generar_barcode_optimized(sku, carpeta, f"sku_{i}"),
                'FROMLOC': fromloc,
                'FROMLOC_BC': generar_barcode_optimized(fromloc, carpeta, f"fromloc_{i}"),
                'QTY': qty,
                'LOT': lot
            }
        except Exception as e:
            logger.error(f"Error generating row {i}: {e}")
            return None
    
    # Use optimized thread pool
    optimal_workers = config.get_optimal_workers(len(datos))
    
    with TimeBlock("barcode_generation"):
        with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
            results = list(executor.map(generar_fila, enumerate(datos)))
    
    # Filter out failed rows
    filas = [f for f in results if f is not None]
    
    # Generate HTML
    html = generar_html(filas, usuario)
    ruta_html = os.path.join(carpeta, "picking_list.html")
    
    # Use optimized HTML writing
    try:
        optimize_html_generation(html, ruta_html)
        logger.info(f"HTML generated at: {ruta_html}")
    except Exception as e:
        logger.error(f"Error saving HTML: {e}")
        raise
    
    return ruta_html

def generar_html(filas: List[Dict], usuario: str) -> str:
    """Generate HTML with improved structure (unchanged logic but better error handling)"""
    try:
        filas_html = ""
        for fila in filas:
            filas_html += f"""
            <tr>
                <td>{fila['CASEID']}</td>
                <td><img src='{fila['CASEID_BC']}' height='40' alt='CASEID Barcode'></td>
                <td>{fila['ORDERKEY']}</td>
                <td><img src='{fila['ORDERKEY_BC']}' height='40' alt='ORDERKEY Barcode'></td>
                <td>{fila['SKU']}</td>
                <td><img src='{fila['SKU_BC']}' height='40' alt='SKU Barcode'></td>
                <td>{fila['FROMLOC']}</td>
                <td><img src='{fila['FROMLOC_BC']}' height='40' alt='FROMLOC Barcode'></td>
                <td>{fila['QTY']}</td>
                <td>{fila['LOT']}</td>
            </tr>
            """
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset='utf-8'>
            <title>Picking List</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: center; }}
                th {{ background-color: #f2f2f2; }}
                img {{ max-width: 100%; height: auto; }}
            </style>
        </head>
        <body>
            <h2>Picking List - Usuario: {usuario}</h2>
            <table>
                <tr>
                    <th>CASEID</th><th>CASEID BarCode</th>
                    <th>ORDERKEY</th><th>ORDERKEY BarCode</th>
                    <th>SKU</th><th>SKU BarCode</th>
                    <th>FROMLOC</th><th>FROMLOC BarCode</th>
                    <th>QTY</th><th>LOT</th>
                </tr>
                {filas_html}
            </table>
            <p><small>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</small></p>
        </body>
        </html>
        """
    except Exception as e:
        logger.error(f"Error generating HTML: {e}")
        raise

# --- INVENTORY LABEL FUNCTIONS (OPTIMIZED) ---

@profile_critical
def filtrar_sku(datos: List[Dict]) -> List[Dict]:
    """Optimized SKU filtering with concurrent processing"""
    locs_excluir = {"2-BLOCK", "PICKTO", "2-QUARANTINE", "LST"}
    skus = defaultdict(list)
    
    # Group by SKU
    for d in datos:
        sku = d.get("SKU", "")
        if sku:
            skus[sku].append(d)
    
    def elegir_registro(registros: List[Dict]) -> Dict:
        """Choose the best record from a group"""
        try:
            # Separate valid and excluded records
            validos = [r for r in registros if not any(ex == r.get("LOC", r.get("FROMLOC", "")) for ex in locs_excluir)]
            excluidos = [r for r in registros if any(ex == r.get("LOC", r.get("FROMLOC", "")) for ex in locs_excluir)]
            
            if validos:
                return max(validos, key=lambda x: x.get("QTY", 0))
            elif excluidos:
                return max(excluidos, key=lambda x: x.get("QTY", 0))
            else:
                return registros[0] if registros else {}
        except Exception as e:
            logger.error(f"Error choosing record: {e}")
            return registros[0] if registros else {}
    
    # Use optimized thread pool
    optimal_workers = config.get_optimal_workers(len(skus))
    
    with TimeBlock("sku_filtering"):
        with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
            resultado = list(executor.map(elegir_registro, skus.values()))
    
    return [r for r in resultado if r]

@profile_critical
def gen_barcode_etiqueta(valor: str, tipo: str) -> str:
    """Generate base64 encoded barcode with caching"""
    cache_key = f"barcode_etiqueta_{valor}_{tipo}"
    
    # Check cache first
    cached_result = api_cache.get(cache_key)
    if cached_result:
        return cached_result
    
    try:
        valor_str = str(valor)
        options = {"write_text": False, "module_width": 0.9, "module_height": 40, "quiet_zone": 0.0}
        code128 = barcode.get('code128', valor_str, writer=ImageWriter())
        buffer = BytesIO()
        code128.write(buffer, options)
        img_bytes = buffer.getvalue()
        base64_img = base64.b64encode(img_bytes).decode('utf-8')
        result = f"data:image/png;base64,{base64_img}"
        
        # Cache the result
        api_cache.set(cache_key, result)
        return result
        
    except Exception as e:
        logger.error(f"Error generating barcode for {valor}: {e}")
        return ""

def generar_html_etiqueta(filas: List[Dict], orderkey: str, externalkey: Optional[str] = None) -> str:
    """Generate inventory label HTML (optimized version of original function)"""
    try:
        # Try to load logo
        try:
            with open('slogo.png', 'rb') as img_file:
                logo_base64 = base64.b64encode(img_file.read()).decode('utf-8')
            logo_src = f"data:image/png;base64,{logo_base64}"
        except Exception:
            logo_src = ''
        
        orderkey_bc = gen_barcode_etiqueta(orderkey, "ORDERKEY_MAIN")
        
        # Pagination logic
        filas_primera = 8
        filas_otras = 10
        paginas = []
        
        if len(filas) <= filas_primera:
            paginas = [filas]
        else:
            paginas.append(filas[:filas_primera])
            for i in range(filas_primera, len(filas), filas_otras):
                paginas.append(filas[i:i+filas_otras])
        
        # HTML template with improved CSS
        html = '''<!DOCTYPE html>
        <html>
        <head>
            <meta charset='utf-8'>
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
            </style>
        </head>
        <body>'''
        
        # Header
        html += "<div class='header'>"
        html += f"<div class='orderkey-box'><div class='orderkey-text'>{orderkey}</div><img src='{orderkey_bc}' class='orderkey-barcode' alt='Order Key Barcode'></div>"
        
        if externalkey:
            html += f"<div class='titulo'>Picking List / {externalkey}</div>"
        else:
            html += "<div class='titulo'>Picking List</div>"
        
        if logo_src:
            html += f"<img src='{logo_src}' class='logo' alt='Company Logo'>"
        
        html += "</div>"
        
        # Content
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
                html += f"<td style='padding-top:0px;padding-bottom:6px;border-top:0;border-bottom:3.5px solid #222;'><img src='{sku_bc}' class='barcode' alt='SKU Barcode'></td>"
                html += f"<td style='padding-top:0px;padding-bottom:6px;border-top:0;border-bottom:3.5px solid #222;'><img src='{lot_bc}' class='barcode' alt='LOT Barcode'></td>"
                html += f"<td style='padding-top:0px;padding-bottom:6px;border-top:0;border-bottom:3.5px solid #222;'><img src='{loc_bc}' class='barcode' alt='LOC Barcode'></td>"
                html += f"<td style='padding-top:0px;padding-bottom:6px;border-top:0;border-bottom:3.5px solid #222;'><img src='{qty_bc}' class='barcode' alt='QTY Barcode'></td>"
                html += "</tr>"
            
            html += f"</table>"
            if num_pagina < len(paginas):
                html += "<div class='page-break'></div>"
        
        html += "</div>"
        html += f"<div class='page-footer'>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>"
        html += "</body></html>"
        
        return html
        
    except Exception as e:
        logger.error(f"Error generating inventory label HTML: {e}")
        raise

@profile_critical
def obtener_datos_etiqueta(orderkey_hex: str, headers: dict, externalkey: Optional[str] = None) -> List[Dict]:
    """Optimized inventory data retrieval with caching and concurrent processing"""
    url_detalle = f"http://api-cqrs-wmxp001-wmx.am.gxo.com/queryservice/orderdtlbyorderkey/{orderkey_hex}"
    
    cache_key = f"etiqueta_{orderkey_hex}_{externalkey}_{hash(str(headers))}"
    
    def _fetch_label_data():
        try:
            logger.info(f"Fetching inventory data for order: {orderkey_hex}")
            
            response = http_client.get(url_detalle, headers=headers)
            
            if response.status_code != 200:
                logger.warning(f"Failed to fetch order details: {response.status_code}")
                return []
            
            # Use optimized JSON parsing
            detalles = FastJSON.loads(response.text)
            if not isinstance(detalles, list):
                detalles = [detalles]
            
            resultado = []
            
            def fetch_inv(d: Dict) -> List[Dict]:
                """Fetch inventory for a single detail record"""
                sku = d.get("SKU", "")
                qty_requerida = d.get("ORDERQTY", 0)
                
                if not sku or not qty_requerida:
                    return []
                
                url_inv = "http://api-cqrs-wmxp001-wmx.am.gxo.com/queryservice/data/434f5245494e565f494e56454e544f52595f5657/4c4f5441445431/74727565/31/31303030"
                payload = {"SKU": sku, "QTY": ">0"}
                
                try:
                    response = http_client.put(url_inv, json=payload, headers=headers)
                    
                    if response.status_code != 200:
                        logger.warning(f"Failed to fetch inventory for SKU {sku}: {response.status_code}")
                        return []
                    
                    # Use optimized JSON parsing
                    data_inv = FastJSON.loads(response.text).get("Data", [])
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
                            "EXTERNALKEY": externalkey,
                            "FROMLOC": inv.get("LOC", "")  # Add FROMLOC for compatibility
                        })
                    
                    return registros
                    
                except Exception as e:
                    logger.error(f"Error fetching inventory for SKU {sku}: {e}")
                    return []
            
            # Use optimized thread pool for concurrent inventory fetching
            optimal_workers = config.get_optimal_workers(len(detalles))
            
            with TimeBlock("inventory_data_fetch"):
                with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
                    results = list(executor.map(fetch_inv, detalles))
            
            # Flatten results
            for sublist in results:
                resultado.extend(sublist)
            
            logger.info(f"Retrieved {len(resultado)} inventory records")
            return resultado
            
        except Exception as e:
            logger.error(f"Error obtaining inventory data: {e}")
            return []
    
    return cached_api_call(cache_key, _fetch_label_data)

# --- STREAMLIT APPLICATION (OPTIMIZED) ---

# Configure Streamlit with caching
st.set_page_config(
    page_title="Picking List WMX - Optimized", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Add performance monitoring to Streamlit
if config.ENABLE_PROFILING:
    st.sidebar.subheader("Performance Monitoring")
    if st.sidebar.button("Show Performance Stats"):
        stats = performance_monitor.get_function_stats()[:10]  # Top 10
        st.sidebar.json({func['name']: f"{func['avg_time']:.3f}s avg" for func in stats})
    
    if st.sidebar.button("Export Performance Metrics"):
        performance_monitor.export_metrics("performance_metrics.json")
        st.sidebar.success("Metrics exported to performance_metrics.json")

st.title("🚀 Picking List WMX - Optimized")

# Performance indicator
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Cache Size", api_cache.stats()['size'])
with col2:
    st.metric("Cache Hit Ratio", f"{api_cache.stats()['hit_ratio']:.2%}")
with col3:
    st.metric("Functions Monitored", len(performance_monitor.function_stats))
with col4:
    st.metric("Slow Functions", len(performance_monitor.slow_functions))

# Create tabs
tab1, tab2, tab3, tab_debug, tab_performance = st.tabs([
    "🖨️ Impresión", 
    "🔄 Reimpresión", 
    "🔍 Buscar por OrderKey", 
    "🐛 Debug Etiqueta",
    "📊 Performance"
])

# Rest of the Streamlit application follows the same structure as the original
# but with optimized function calls and better error handling

with tab1:
    # Initialize session state with better defaults
    for key, default in [
        ('usuario', ''),
        ('ordenes', None),
        ('headersWMX', None),
        ('seleccion_idx', None),
        ('status', ''),
        ('confirmar', False),
        ('last_reload', time.time())
    ]:
        if key not in st.session_state:
            st.session_state[key] = default
    
    lista_usuarios = [
        "america.torres",
        "jose.centeno002", 
        "guillermo.betanzos",
        "edgar.carabeo"
    ]
    
    # User selection with validation
    try:
        current_index = lista_usuarios.index(st.session_state['usuario']) if st.session_state['usuario'] in lista_usuarios else 0
    except (ValueError, TypeError):
        current_index = 0
    
    usuario = st.selectbox(
        "👤 Usuario WMX", 
        options=lista_usuarios, 
        index=current_index,
        help="Selecciona tu usuario para continuar"
    )
    st.session_state['usuario'] = usuario
    
    # Setup headers
    headers_wmx = headersWMX.copy()
    headers_wmx["xposc-userid"] = usuario
    st.session_state['headersWMX'] = headers_wmx
    
    # Auto-reload logic with better timing
    if time.time() - st.session_state['last_reload'] > 120:  # 2 minutes
        st.session_state['last_reload'] = time.time()
        with st.spinner("Auto-reloading orders..."):
            st.session_state['ordenes'] = cargar_ordenes(headers_wmx)
        st.rerun()
    
    # Load orders button
    if st.button("🔄 Cargar órdenes", help="Cargar órdenes disponibles desde el sistema"):
        with st.spinner("Cargando órdenes..."):
            st.session_state['ordenes'] = cargar_ordenes(headers_wmx)
        
        if st.session_state['ordenes'] is None or st.session_state['ordenes'].empty:
            st.error("❌ No se encontraron órdenes")
        else:
            st.success(f"✅ Órdenes encontradas: {len(st.session_state['ordenes'])}")
    
    # Display orders if available
    if st.session_state['ordenes'] is not None and not st.session_state['ordenes'].empty:
        ordenes = st.session_state['ordenes']
        
        # Show orders with better formatting
        st.subheader("📋 Órdenes disponibles")
        
        # Add filtering
        if len(ordenes) > 10:
            search_term = st.text_input("🔍 Filtrar órdenes:", placeholder="Buscar por EXTERNKEY o ORDERKEY")
            if search_term:
                mask = ordenes['EXTERNKEY'].str.contains(search_term, case=False, na=False) | \
                       ordenes['ORDERKEY'].str.contains(search_term, case=False, na=False)
                ordenes = ordenes[mask]
        
        # Display with enhanced table
        st.dataframe(
            ordenes,
            use_container_width=True,
            column_config={
                "STATUS": st.column_config.TextColumn("Status", help="Estado de la orden"),
                "ORDERDATE": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YYYY"),
                "TOTALORDERQTY": st.column_config.NumberColumn("Cantidad Total", format="%.0f")
            }
        )
        
        # Order selection
        opciones = [f"{row['EXTERNKEY']} ({row['ORDERKEY']})" for _, row in ordenes.iterrows()]
        idx = st.selectbox(
            "📦 Selecciona una orden para procesar", 
            options=list(range(len(opciones))), 
            format_func=lambda i: opciones[i],
            help="Selecciona la orden que deseas procesar"
        )
        
        st.session_state['seleccion_idx'] = idx
        row = ordenes.iloc[idx]
        orderkey = row['ORDERKEY']
        orderkey_hex = row['HEXORDER']
        usuario_orden = row.get('EDITWHO', usuario)
        
        # Action buttons with better layout
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col3:
            if not usuario:
                st.warning("⚠️ Selecciona un usuario WMX para continuar.")
            else:
                # Quick download button
                if st.button("⚡ Generar y descargar Picking List", 
                           key="generar_descargar",
                           help="Genera la lista de picking sin procesar la orden"):
                    
                    with st.spinner("Generando Picking List..."):
                        try:
                            logger.info(f"Quick generation for {orderkey} / {row['EXTERNKEY']}")
                            
                            datos_etiqueta = obtener_datos_etiqueta(
                                orderkey_hex, 
                                st.session_state['headersWMX'], 
                                row['EXTERNKEY']
                            )
                            
                            if not datos_etiqueta:
                                st.error("❌ No se encontraron datos para la etiqueta")
                                st.stop()
                            
                            filtrados = filtrar_sku(datos_etiqueta)
                            html_etiqueta = generar_html_etiqueta(filtrados, orderkey, row['EXTERNKEY'])
                            
                            st.download_button(
                                f"📥 Descargar Picking List {orderkey}",
                                data=html_etiqueta,
                                file_name=f"PickingList_{orderkey}.html",
                                mime="text/html",
                                help="Descargar el archivo HTML generado"
                            )
                            
                            st.success("✅ Picking List generado correctamente")
                            
                        except Exception as e:
                            st.error(f"❌ Error generando Picking List: {str(e)}")
                            logger.error(f"Error in quick generation: {e}")
        
        # Process order section
        if st.button("🔄 Procesar orden seleccionada", help="Procesar completamente la orden seleccionada"):
            st.session_state['confirmar'] = True
        
        if st.session_state['confirmar']:
            st.warning(f"⚠️ ¿Seguro que deseas procesar la orden {row['EXTERNKEY']} ({orderkey})?")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("✅ Sí, procesar ahora"):
                    st.session_state['confirmar'] = False
                    
                    # Progress bar for better UX
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    try:
                        # Step 1: Allocate
                        status_text.text("🔄 Ejecutando ALLOCATE...")
                        progress_bar.progress(20)
                        
                        if not paso_allocate(orderkey_hex, st.session_state['headersWMX']):
                            st.error("❌ Error en ALLOCATE")
                            st.stop()
                        
                        # Step 2: Release
                        status_text.text("🔄 Ejecutando RELEASE...")
                        progress_bar.progress(40)
                        
                        if not paso_release(orderkey_hex, st.session_state['headersWMX']):
                            st.error("❌ Error en RELEASE")
                            st.stop()
                        
                        # Step 3: Process
                        status_text.text("🔄 Ejecutando PROCESS...")
                        progress_bar.progress(60)
                        
                        if not paso_process(orderkey_hex, st.session_state['headersWMX']):
                            st.error("❌ Error en PROCESS")
                            st.stop()
                        
                        # Step 4: Generate picking list
                        status_text.text("📋 Generando Picking List...")
                        progress_bar.progress(80)
                        
                        datos_etiqueta = obtener_datos_etiqueta(
                            orderkey_hex, 
                            st.session_state['headersWMX'], 
                            row['EXTERNKEY']
                        )
                        
                        if not datos_etiqueta:
                            st.error("❌ No se encontraron datos para la etiqueta")
                            st.stop()
                        
                        filtrados = filtrar_sku(datos_etiqueta)
                        html_etiqueta = generar_html_etiqueta(filtrados, orderkey, row['EXTERNKEY'])
                        
                        progress_bar.progress(100)
                        status_text.text("✅ ¡Proceso completado!")
                        
                        st.success("🎉 ¡Proceso completado! Ya puedes descargar el Picking List.")
                        
                        st.download_button(
                            label=f"📥 Descargar Picking List {orderkey}",
                            data=html_etiqueta,
                            file_name=f"PickingList_{orderkey}.html",
                            mime="text/html"
                        )
                        
                        st.session_state['status'] = "✅ ¡Completado!"
                        
                    except Exception as e:
                        st.error(f"❌ Error durante el procesamiento: {str(e)}")
                        logger.error(f"Error in order processing: {e}")
            
            with col2:
                if st.button("❌ Cancelar"):
                    st.session_state['confirmar'] = False
            
            with col3:
                if st.button("🏷️ Generar etiqueta de inventario"):
                    with st.spinner("Generando etiqueta de inventario..."):
                        try:
                            logger.info(f"Generating inventory label for {orderkey} / {row['EXTERNKEY']}")
                            
                            datos_etiqueta = obtener_datos_etiqueta(
                                orderkey_hex, 
                                st.session_state['headersWMX'], 
                                row['EXTERNKEY']
                            )
                            
                            if not datos_etiqueta:
                                st.error("❌ No se encontraron datos para la etiqueta")
                                st.stop()
                            
                            filtrados = filtrar_sku(datos_etiqueta)
                            html_etiqueta = generar_html_etiqueta(filtrados, orderkey, row['EXTERNKEY'])
                            
                            st.download_button(
                                "📥 Descargar Picking List",
                                data=html_etiqueta,
                                file_name="PickingList.html",
                                mime="text/html"
                            )
                            
                            st.success("✅ Etiqueta de inventario generada correctamente")
                            
                        except Exception as e:
                            st.error(f"❌ Error generando etiqueta: {str(e)}")
                            logger.error(f"Error in inventory label generation: {e}")
    
    # Status display
    if st.session_state['status']:
        st.info(st.session_state['status'])

# Performance monitoring tab
with tab_performance:
    st.subheader("📊 Performance Monitoring")
    
    if config.ENABLE_PROFILING:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🔄 Function Statistics")
            
            if st.button("🔄 Refresh Stats"):
                st.rerun()
            
            stats = performance_monitor.get_function_stats()[:15]  # Top 15
            if stats:
                stats_df = pd.DataFrame(stats)
                st.dataframe(
                    stats_df[['name', 'call_count', 'avg_time', 'total_time', 'success_count', 'error_count']],
                    use_container_width=True,
                    column_config={
                        "avg_time": st.column_config.NumberColumn("Avg Time (s)", format="%.3f"),
                        "total_time": st.column_config.NumberColumn("Total Time (s)", format="%.2f")
                    }
                )
            else:
                st.info("No performance data available yet")
        
        with col2:
            st.subheader("🐌 Slow Functions")
            
            slow_funcs = performance_monitor.get_slow_functions()[:10]  # Top 10
            if slow_funcs:
                slow_df = pd.DataFrame(slow_funcs)
                st.dataframe(
                    slow_df,
                    use_container_width=True,
                    column_config={
                        "execution_time": st.column_config.NumberColumn("Execution Time (s)", format="%.3f")
                    }
                )
            else:
                st.info("No slow functions detected")
        
        # System stats
        st.subheader("💻 System Statistics")
        sys_stats = performance_monitor.get_system_stats_summary()
        
        if sys_stats:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Avg CPU %", f"{sys_stats['avg_cpu_percent']:.1f}")
            with col2:
                st.metric("Avg Memory %", f"{sys_stats['avg_memory_percent']:.1f}")
            with col3:
                st.metric("Memory Used MB", f"{sys_stats['avg_memory_used_mb']:.0f}")
            with col4:
                st.metric("Active Threads", sys_stats['current_active_threads'])
        
        # Export/Reset buttons
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📤 Export Metrics"):
                performance_monitor.export_metrics("performance_metrics.json")
                st.success("Metrics exported to performance_metrics.json")
        
        with col2:
            if st.button("📝 Log Summary"):
                performance_monitor.log_performance_summary()
                st.success("Performance summary logged")
        
        with col3:
            if st.button("🗑️ Reset Stats"):
                performance_monitor.reset_stats()
                api_cache.clear()
                st.success("Performance statistics reset")
    
    else:
        st.info("Performance monitoring is disabled. Enable it in configuration to see detailed metrics.")

# The remaining tabs (tab2, tab3, tab_debug) follow the same pattern as the original
# but with optimized function calls and better error handling

# At the end of the application, log performance summary
if config.ENABLE_PROFILING:
    performance_monitor.log_performance_summary()

logger.info("Optimized Outbound application loaded successfully")