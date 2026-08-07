# Hosting Agent SDK (Deploy ke Produksi)

Panduan ini menjelaskan cara menjalankan **Agent SDK** di produksi pada infrastruktur
Anda sendiri (*self-hosting*): model subprocess, pola sesi, penyediaan kontainer, serta
hal-hal produksi seperti persistensi, observabilitas, autentikasi, dan isolasi
multi-tenant untuk Docker, Kubernetes, dan penyedia *sandbox*.

> **Ringkas:** Agent SDK **memunculkan dan mengawasi sebuah subprocess CLI `claude`**
> yang memiliki shell, direktori kerja, dan berkas sesi di disk lokal. Menghosting-nya
> **tidak sama** dengan menghosting pembungkus API tanpa status (*stateless*). Setiap
> agen yang berjalan adalah proses berumur panjang yang terikat ke state lokal — inilah
> yang menentukan cara Anda mengalokasikan sumber daya, mem-persist sesi, dan melakukan
> penskalaan lintas tenant.

> Jika Anda **tidak** butuh kontrol infrastruktur, isolasi khusus, atau *data plane*
> sendiri, pertimbangkan **Managed Agents** — REST API terkelola tempat Anthropic
> menjalankan agen dan sandbox-nya, tanpa infrastruktur hosting yang perlu Anda operasikan.

---

## 1. Model Subprocess

Saat kode Anda memanggil `query()`, SDK **memunculkan proses CLI `claude` terpisah** dan
berkomunikasi dengannya lewat *stdio*. Subprocess itulah yang memiliki shell, direktori
kerja, dan transkrip sesi (JSONL) di disk lokal.

- **Satu sesi agen = satu subprocess.** Menjalankan N sesi bersamaan berarti N
  subprocess, masing-masing dengan pohon proses dan berkas transkripnya sendiri.
- Secara *default*, semua subprocess mewarisi direktori kerja aplikasi Anda. Oleh karena
  itu, berikan `cwd` di setiap panggilan `query()` bila tiap sesi butuh filesystem
  terpisah:

```typescript
// TypeScript
query({ prompt, options: { cwd: "/work/session-a" } })
```

```python
# Python
query(prompt=prompt, options=ClaudeAgentOptions(cwd="/work/session-a"))
```

### State yang berada di disk lokal

Tiga jenis state agen tersimpan di filesystem kontainer secara *default*. **Tidak satu
pun** yang bertahan setelah kontainer di-restart, di-*scale-down*, atau berpindah node.

| State | Lokasi default |
|-------|----------------|
| Transkrip sesi | `~/.claude/projects/`, atau `projects/` di bawah `CLAUDE_CONFIG_DIR` bila diset |
| Berkas memori `CLAUDE.md` | `~/.claude/CLAUDE.md` (tier user) dan direktori kerja sesi (tier project) |
| Artefak direktori kerja | Direktori kerja sesi |

> Untuk mem-persist transkrip lintas host, konfigurasikan **adapter `SessionStore`**.
> Berkas memori dan artefak direktori kerja lain butuh strategi penyimpanan tersendiri,
> misalnya *volume* yang di-mount atau sinkronisasi ke *object store*.

## 2. Memilih Pola Sesi

Empat pola berikut menentukan siklus hidup sesi: berapa lama kontainer hidup relatif
terhadap sesi yang dilayaninya.

### A. Sesi Ephemeral (sekali pakai)

Buat satu kontainer per tugas pengguna, hancurkan saat tugas selesai. Cocok untuk tugas
sekali jalan: investigasi & perbaikan bug, ekstraksi faktur/kwitansi, terjemahan
dokumen, transformasi media. Kontainer menjalankan *entrypoint* sekali-jalan yang
memanggil SDK lalu keluar.

```typescript
// TypeScript — simpan sebagai entrypoint.mts atau set "type":"module"
import { query } from "@anthropic-ai/claude-agent-sdk";

const prompt = process.env.TASK_PROMPT!;
for await (const message of query({ prompt, options: { maxTurns: 20 } })) {
  console.log(message);
}
```

### B. Sesi Long-running (berumur panjang)

Jalankan instans kontainer persisten — sering meng-host banyak proses SDK per kontainer
— untuk melayani pekerjaan berkelanjutan. Cocok untuk agen yang bertindak otonom,
menyajikan konten, atau menangani aliran pesan bervolume tinggi (mis. agen email, site
builder per-pengguna, chat bot Slack). Kontainer mengekspos endpoint HTTP/WebSocket dan
memetakan tiap sesi aktif ke satu `query` berumur panjang.

- **TypeScript:** gunakan `streamInput()` untuk menambah giliran ke sesi aktif dan
  `startup()` untuk *pre-warm* subprocess sebelum trafik masuk.
- **Python:** gunakan `ClaudeSDKClient` untuk menahan sesi tetap terbuka lintas giliran.
- Ukur kontainer agar mampu menampung jumlah maksimum sesi bersamaan di memori.

### C. Sesi Hybrid

Kontainer ephemeral yang **melakukan hidrasi dari `SessionStore`** saat *startup* dan
mem-persist pembaruan kembali. Cocok untuk sesi yang melintasi banyak interaksi tetapi
menganggur di antaranya (project manager pribadi, riset mendalam yang jeda-lanjut, agen
dukungan pelanggan). `SessionStore` **wajib** untuk pola ini — mematikan kontainer tanpa
store akan menghilangkan transkrip bersamanya.

```typescript
// TypeScript
for await (const message of query({
  prompt: userInput,
  options: { resume: sessionId, sessionStore },
})) {
  // ...
}
```

```python
# Python
async for message in query(
    prompt=user_input,
    options=ClaudeAgentOptions(resume=session_id, session_store=session_store),
):
    ...
```

### D. Kontainer Multi-agen

Jalankan beberapa subprocess SDK di dalam satu kontainer. Cocok untuk agen yang harus
berkolaborasi erat (mis. simulasi multi-agen di lingkungan bersama). Beri **tiap agen
direktori kerja sendiri** agar tidak saling menimpa berkas, dan isolasi pemuatan setelan
supaya `CLAUDE.md` per-agen tidak bocor antar agen.

## 3. Menyediakan Kontainer

### Sandboxing berbasis kontainer

Jalankan SDK di dalam kontainer ber-*sandbox* untuk isolasi proses, batas sumber daya,
kontrol jaringan, dan filesystem ephemeral. Pertanyaan saat memilih penyedia:

- **Siapa yang menjalankan sandbox** — layanan (*sandbox-as-a-service*) atau
  di-*self-host*.
- **Latensi cold-start** — pola ephemeral butuh start sub-detik; long-running lebih toleran.
- **Penyimpanan persisten** — pola hybrid butuh storage durabel di suatu tempat.
- **Model harga** — per-detik cocok untuk beban ephemeral yang *bursty*; per-jam untuk long-running.
- **Jaringan** — dukungan aturan egress kustom, proxy keluar, dan *peering* VPC privat.

Penyedia untuk dievaluasi: **Modal Sandbox**, **Cloudflare Sandboxes**, **Daytona**,
**E2B**, **Fly Machines**, **Vercel Sandbox**. Untuk opsi self-hosted (Docker, gVisor,
Firecracker), lihat dokumen *Isolation Technologies*.

### Dependensi runtime

- **Python 3.10+** untuk Python SDK, atau **Node.js 18+** untuk TypeScript SDK.
- Kedua SDK mem-*bundle* binari Claude Code native untuk sebagian besar instalasi;
  CLI yang dimunculkan tidak butuh instalasi Node.js terpisah.
- Binari yang di-bundle **dipatok ke versi paket SDK** — memperbarui SDK adalah cara
  memperbarui CLI. SDK mengikuti *semver*: ambil rilis patch terus-menerus, tinjau
  changelog sebelum mengambil rilis minor.

### Sumber daya

**1 GiB RAM, 5 GiB disk, 1 CPU per agen** adalah titik awal wajar untuk instans yang
baru dijalankan. Penggunaan memori tumbuh seiring panjang sesi dan aktivitas tool, jadi
ukurlah untuk panjang sesi & konkurensi nyata, bukan hanya baseline saat idle.

### Jaringan

- **Keluar (outbound):** HTTPS ke `api.anthropic.com` — atau endpoint regional penyedia
  Anda saat memakai Amazon Bedrock / Google Cloud. Bila agen memakai server MCP atau tool
  eksternal, izinkan akses keluar ke endpoint tersebut. Untuk produksi, rutekan trafik
  keluar lewat *egress proxy* yang menegakkan allowlist domain, menyuntikkan kredensial,
  dan mencatat permintaan.
- **Masuk (inbound):** ekspos port HTTP/WebSocket pada kontainer. Aplikasi Anda menangani
  permintaan klien di port itu dan memanggil SDK secara internal; subprocess-nya sendiri
  **tidak** mendengarkan jaringan.

## 4. Hal-hal Produksi

### Persistensi sesi & state

Disk lokal default hilang saat restart/scale-down/pindah node. Untuk sesi yang
diharapkan bisa dilanjutkan pengguna, **cerminkan transkrip ke storage durabel** dengan
adapter `SessionStore` (tersedia referensi S3, Redis, Postgres). Tiga hal penting:

- **Hanya transkrip:** `SessionStore` mencerminkan transkrip, **bukan** berkas memori
  `CLAUDE.md` atau artefak direktori kerja lain — mount volume bersama atau sinkron
  terpisah.
- **Cermin, bukan pengganti:** subprocess menulis ke disk lokal lebih dulu; store
  menerima salinan tiap batch. Tulisan lokal tetap otoritatif.
- **Pesan `mirror_error`:** batch yang ditolak dikirim ulang hingga tiga kali (dengan
  *backoff* singkat; panggilan yang *timeout* tidak diulang). Bila tetap gagal, SDK
  membuang batch, memancarkan pesan `{ type: "system", subtype: "mirror_error" }`, lalu
  melanjutkan query. **Pasang alert** bila durabilitas store penting.

### Observabilitas

SDK mewarisi konfigurasi **OpenTelemetry** dari environment. Set variabel OTEL di level
kontainer/orkestrator agar setiap `query()` mengekspor span, metrik, dan log ke collector
Anda:

```bash
CLAUDE_CODE_ENABLE_TELEMETRY=1
CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1   # hanya perlu untuk traces
OTEL_TRACES_EXPORTER=otlp
OTEL_METRICS_EXPORTER=otlp
OTEL_LOGS_EXPORTER=otlp
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_EXPORTER_OTLP_ENDPOINT=http://collector.example.com:4318
```

> Teks prompt dan input tool **tidak** disertakan dalam ekspor secara default. Lihat
> dokumen *Observability* untuk flag opt-in dan katalog sinyal lengkap.

### Autentikasi & rahasia

- **API Anthropic:** subprocess membaca `ANTHROPIC_API_KEY` dari environment-nya. Suplai
  dari secret manager, atau set `ANTHROPIC_BASE_URL` untuk merutekan panggilan model lewat
  proxy yang menyuntikkan kunci di luar kontainer.
- **Masuk (inbound):** letakkan autentikasi di *gateway* di depan kontainer agen. Agen
  seharusnya menerima permintaan yang sudah ter-autentikasi, bukan komponen yang
  memvalidasi token pengguna.
- **Tool keluar (outbound):** jaga kredensial tool **di luar** environment agen. Rutekan
  panggilan keluar lewat proxy yang menyuntikkan API key setelah permintaan meninggalkan
  kontainer.

### Penskalaan & konkurensi

Tiap sesi berjalan di subprocess-nya sendiri, jadi konkurensi per host dibatasi oleh
berapa banyak subprocess yang muat di RAM-nya.

```text
agen per host = (RAM host - overhead) / (plafon RAM per-sesi)
```

Ukur plafon per-sesi dengan menjalankan sesi representatif ke panjang target di bawah
beban tool yang diharapkan, lalu catat **puncak RSS**. Titik awal 1 GiB adalah *lantai*,
bukan *plafon*.

Untuk penskalaan horizontal pada pola long-running, jalankan *pool* kontainer di belakang
*load balancer* dan **pin tiap sesi ke satu kontainer** memakai *consistent hashing* pada
`sessionId`. Fanout besar subagen bersamaan dari satu sesi bisa menabrak *rate limit* —
pecah pekerjaan menjadi batch lebih kecil.

### Biaya

Biaya token Anthropic biasanya **mendominasi** biaya infrastruktur kontainer, sering satu
orde besaran atau lebih. Kontainer minimal berjalan ~$0,05/jam, sementara satu sesi agen
panjang bisa menghabiskan dolar dalam token. Lihat *Cost tracking* untuk akuntansi token
per-sesi.

### Isolasi multi-tenant

Secara default SDK membaca setelan dan berkas memori `CLAUDE.md` dari filesystem. Di
kontainer bersama yang melayani banyak tenant, berkas itu bisa membocorkan konteks satu
tenant ke sesi tenant lain. Untuk mengisolasi tenant dalam satu kontainer:

- Berikan `settingSources: []` (TS) atau `setting_sources=[]` (Python) agar **tak ada**
  setelan filesystem yang dimuat.
- Set `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` di `env`. *Auto memory* dimuat ke system prompt
  **terlepas** dari `settingSources`.
- Arahkan `CLAUDE_CONFIG_DIR` ke direktori per-tenant agar tenant tidak berbagi
  `~/.claude.json` global.
- Gunakan direktori kerja per-tenant — berikan `cwd` secara eksplisit di **setiap**
  `query()`.
- Terapkan aturan egress per-tenant di proxy Anda (IP keluar, kredensial, atau allowlist
  domain berbeda) agar tenant yang tersusupi tak bisa meng-eksfiltrasi lewat kebijakan
  keluar tenant lain.

```typescript
// TypeScript — env MENGGANTIKAN environment subprocess; sebarkan ...process.env
for await (const message of query({
  prompt,
  options: {
    cwd: tenantDir,
    settingSources: [],
    env: {
      ...process.env,
      CLAUDE_CONFIG_DIR: configDir,
      CLAUDE_CODE_DISABLE_AUTO_MEMORY: "1",
    },
  },
})) {
  // ...
}
```

```python
# Python — env DI-MERGE di atas environment yang diwarisi
async for message in query(
    prompt=prompt,
    options=ClaudeAgentOptions(
        cwd=tenant_dir,
        setting_sources=[],
        env={
            "CLAUDE_CONFIG_DIR": config_dir,
            "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
        },
    ),
):
    ...
```

## 5. Batasan yang Diketahui

| Batasan | Yang harus dilakukan |
|---------|----------------------|
| Tidak ada *timeout* sesi tingkat atas | Sesi tidak mati sendiri. Set `maxTurns` di `Options` untuk membatasi jumlah putaran penggunaan tool. |
| Pertumbuhan memori pada sesi panjang | Batasi panjang sesi atau daur-ulang subprocess secara berkala. |
| Fanout subagen paralel besar dapat kena rate limit | Pecah pekerjaan menjadi batch lebih kecil, bukan satu dispatch lebar. |
| Tidak ada tenggat *wall-clock* per-subagen | Batasi tiap subagen dengan `maxTurns` di `AgentDefinition`. Untuk subagen background, `CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS` memasang *watchdog* saat subagen `run_in_background` berhenti menghasilkan output (bukan tenggat total runtime). |

---

## Ceklis kesiapan produksi

- [ ] `SessionStore` dikonfigurasi untuk sesi yang perlu bisa dilanjutkan (pola hybrid: wajib).
- [ ] Berkas `CLAUDE.md` / artefak direktori kerja punya strategi storage terpisah.
- [ ] `cwd` diberikan eksplisit per sesi/tenant agar filesystem terpisah.
- [ ] Variabel OTEL diset di level kontainer untuk ekspor trace/metrik/log.
- [ ] Alert dipasang untuk pesan `mirror_error`.
- [ ] `ANTHROPIC_API_KEY` disuplai dari secret manager, bukan di-hardcode.
- [ ] Autentikasi inbound di gateway; kredensial tool keluar disuntik lewat proxy.
- [ ] Plafon RAM per-sesi diukur (puncak RSS) dan agen-per-host dihitung.
- [ ] Isolasi multi-tenant diaktifkan bila satu kontainer melayani banyak tenant.
- [ ] `maxTurns` diset untuk membatasi sesi & subagen (tidak ada timeout otomatis).

## Referensi

- [Hosting the Agent SDK — Claude Docs](https://code.claude.com/docs/en/agent-sdk/hosting)
- [Hosting cookbook (Docker, Modal, Kubernetes)](https://github.com/anthropics/claude-cookbooks/tree/main/claude_agent_sdk/hosting)
- [Session storage — Claude Docs](https://code.claude.com/docs/en/agent-sdk/session-storage)
- [Observability — Claude Docs](https://code.claude.com/docs/en/agent-sdk/observability)
- [Secure deployment — Claude Docs](https://code.claude.com/docs/en/agent-sdk/secure-deployment)
- [Cost tracking — Claude Docs](https://code.claude.com/docs/en/agent-sdk/cost-tracking)
- [Managed Agents overview — Claude Platform Docs](https://platform.claude.com/docs/en/managed-agents/overview)
