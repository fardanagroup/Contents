# Menghubungkan Remote MCP dari Cloud Anthropic (Setup Firewall)

Panduan ini menjelaskan cara kerja **custom connector (Remote MCP)** yang terhubung
melalui infrastruktur cloud Anthropic, syarat aksesibilitas internet yang berlaku, dan
cara mengatasi kegagalan koneksi ketika server MCP Anda berada di belakang firewall
atau jaringan privat.

> **Ringkas:** Koneksi ke server MCP Anda ditarik dari cloud Anthropic, bukan dari
> perangkat lokal. Oleh karena itu server MCP Anda harus dapat dijangkau dari internet
> publik. Jika berada di belakang firewall, tambahkan rentang IP Anthropic ke daftar
> izin (*allowlist*) — atau gunakan MCP Tunnels sebagai alternatif tanpa membuka port
> masuk.

---

## 1. Menggunakan Infrastruktur Cloud (Remote MCP)

Untuk **custom connectors**, konektor terhubung ke server MCP Anda **langsung dari cloud
Anthropic**, bukan dari perangkat lokal Anda.

Hal ini **tetap berlaku** meskipun Anda menggunakan aplikasi lokal seperti **Claude
Desktop** atau **Cowork**. Artinya, alamat lokal (`localhost`, `127.0.0.1`) atau server
yang hanya bisa diakses dari dalam jaringan Anda **tidak akan berfungsi** untuk custom
connector jenis ini — karena permintaan tidak berasal dari mesin Anda, melainkan dari
cloud Anthropic.

## 2. Syarat Aksesibilitas Internet

Karena koneksi ditarik dari cloud Anthropic, server MCP Anda **wajib dapat dijangkau
melalui internet publik**. Pastikan:

- Server MCP memiliki alamat/URL publik yang dapat diakses (mis. `https://mcp.contoh.com`).
- Menggunakan **HTTPS** dengan sertifikat TLS yang valid.
- DNS publik dapat me-resolve domain server MCP Anda.
- Endpoint benar-benar merespons dari luar jaringan Anda (uji dari jaringan berbeda,
  bukan hanya dari kantor/VPN).

## 3. Solusi untuk Jaringan Privat (Firewall)

Jika server MCP Anda berada di belakang **firewall perusahaan** atau **jaringan
privat**, koneksi dari cloud Anthropic akan **gagal (timeout)** karena lalu lintas masuk
diblokir.

Untuk mengatasinya, Anda punya dua opsi:

### Opsi A — Allowlist rentang IP Anthropic (rekomendasi utama)

Tambahkan rentang IP **outbound** Anthropic ke daftar izin (*allowlist*) firewall Anda
agar koneksi masuk dari Claude dapat menjangkau server MCP Anda dengan aman.

Anthropic menggunakan alamat IP tetap yang tidak akan berubah tanpa pemberitahuan.
Untuk memanggil server MCP Anda, gunakan rentang **Outbound** berikut:

| Jenis | Rentang IP |
|-------|-----------|
| Outbound IPv4 (dipakai untuk panggilan MCP connector) | `160.79.104.0/21` |

> Rentang **Inbound** Anthropic (`160.79.104.0/23` untuk IPv4 dan `2607:6bc0::/48`
> untuk IPv6) adalah tempat Anthropic **menerima** koneksi, bukan sumber panggilan
> keluar ke server MCP Anda. Untuk allowlist firewall server MCP, yang relevan adalah
> rentang **Outbound** di atas.

**Alamat IP yang sudah tidak digunakan (hapus dari firewall jika pernah di-allowlist):**

```text
34.162.46.92/32
34.162.102.82/32
34.162.136.91/32
34.162.142.92/32
34.162.183.95/32
```

> ⚠️ **Selalu verifikasi rentang terbaru** di halaman resmi sebelum menerapkan aturan
> firewall — daftar ini dapat diperbarui oleh Anthropic. Lihat
> [IP addresses — Claude Platform Docs](https://platform.claude.com/docs/en/api/ip-addresses).

### Opsi B — Gunakan MCP Tunnels (tanpa membuka port masuk)

Jika Anda **tidak ingin** membuka port masuk atau meng-*allowlist* IP Anthropic, gunakan
**MCP Tunnels**. Lalu lintas mengalir lewat koneksi **keluar-saja (outbound-only)**,
sehingga Anda **tidak perlu**:

- membuka port inbound di firewall,
- mengekspos layanan ke internet publik, atau
- meng-*allowlist* rentang IP Anthropic di server asal.

Lihat [MCP tunnels — Claude Platform Docs](https://platform.claude.com/docs/en/agents-and-tools/mcp-tunnels/overview).

---

## Ceklis pemecahan masalah (timeout / koneksi gagal)

- [ ] Server MCP dapat diakses dari internet publik (uji dari jaringan luar).
- [ ] Menggunakan HTTPS dengan sertifikat TLS valid.
- [ ] Rentang IP **outbound** Anthropic sudah ada di allowlist firewall.
- [ ] Alamat IP lama (phased out) sudah dihapus dari aturan firewall.
- [ ] Bukan menggunakan `localhost`/alamat privat untuk custom connector.
- [ ] Alternatif: pertimbangkan **MCP Tunnels** jika allowlisting tidak memungkinkan.

## Referensi

- [IP addresses — Claude Platform Docs](https://platform.claude.com/docs/en/api/ip-addresses)
- [Get started with custom connectors using remote MCP — Claude Help Center](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp)
- [MCP tunnels — Claude Platform Docs](https://platform.claude.com/docs/en/agents-and-tools/mcp-tunnels/overview)
