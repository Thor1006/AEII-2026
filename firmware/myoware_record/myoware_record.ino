/*
  MyoWare 2.0 Wireless Shield - RECORD mode for the TrueRehab-RF recorder (recorder/record.py) and the Pi bridge.
  The demo sketch (firmware/myoware_demo) is for watching; this one is for recording. It sends every sample with
  the ESP32's own microsecond clock, so the receiver can undo delivery jitter:
    E,<micros>,<raw>,<env>                 1000 per second  (sEMG)
    I,<micros>,ax,ay,az,gx,gy,gz           200 per second   (MPU6050, only if USE_IMU is 1)
    # ...                                  header and a status line every 5 s (ignored as data)
  Why RAW too: the envelope (ENV) shows how hard the muscle works, but the classic fatigue sign, a drop in the
  signal's median frequency, needs the raw signal sampled at >= 1 kHz.

  How the data leaves the board (every line always goes to USB too, 921600 baud, for bench tests):
    WIFI_LINK 1 (default): joins your Wi-Fi as truerehab-myoware.local and serves one TCP client on port 3334:
               python record.py --emg tcp://truerehab-myoware.local:3334   (or the Pi bridge's emg provider)
               Needs wifi_secrets.h next to this file: copy wifi_secrets.example.h and fill it in (git-ignored).
               Same design as the IMU board's fw 2.1 (verified 2026-11-05): sampling on core 1 never waits for
               the network; a core-0 task sends whole lines from a 64 KB buffer (~2.7 s of data at 1 kHz).
    WIFI_LINK 0: Bluetooth Classic serial "TrueRehab-MyoWare" instead (the Nov-4 Mac link didn't connect).
  RAW (GPIO36) and ENV (GPIO39) are on ADC1, which keeps working while Wi-Fi is on (ADC2 doesn't).

  Hardware: MyoWare 2.0 Muscle Sensor + MyoWare 2.0 Wireless Shield (ESP32-WROOM).
  Arduino IDE / arduino-cli: "esp32" boards package (Espressif), board "ESP32 Dev Module" (esp32:esp32:esp32).
  SAFETY (SparkFun's warning): do not have the shield on a person while USB-C is plugged in (programming or
  charging). For recordings on a person: unplug USB and run on the battery; the data goes over Wi-Fi.

  On the board since 2026-11-07 (Wi-Fi link verified: CLAUDE/output/2026-11-07-1601-myoware-upload.md).
  2026-11-08 (compiled, not yet uploaded): the status line adds link_stall_ms and link_buf_max, and the Wi-Fi
  packets are marked CS4 (see CLAUDE/plans/2026-11-08-wifi-drop-fixes.md).
*/

#include <Wire.h>

#ifndef WIFI_LINK
#define WIFI_LINK 1  // 1 = Wi-Fi TCP link (port 3334); 0 = Bluetooth serial
#endif
#ifndef USE_IMU
#define USE_IMU 0    // 1 = read an MPU6050 on I2C (set the pins below to the ones you wired)
#endif

#if WIFI_LINK
#if __has_include("wifi_secrets.h")
#include "wifi_secrets.h"
#else
#error "WIFI_LINK 1 needs wifi_secrets.h next to the .ino: copy wifi_secrets.example.h to wifi_secrets.h and fill in your Wi-Fi name and password (or build with -DWIFI_LINK=0 for Bluetooth)"
#endif
#include <WiFi.h>
#include <ESPmDNS.h>
#include <freertos/stream_buffer.h>
#include <lwip/sockets.h>  // IP_TOS
const char *LINK_HOSTNAME = "truerehab-myoware";  // reachable as truerehab-myoware.local
constexpr uint16_t LINK_PORT = 3334;
constexpr size_t LINK_BUF_BYTES = 65536;  // ~2.7 s of 1-kHz output, kept while Wi-Fi stalls
constexpr uint32_t LINK_REJOIN_MS = 15000;  // not joined after this long: start joining again
#else
#include "BluetoothSerial.h"
BluetoothSerial SerialBT;
const char *BT_NAME = "TrueRehab-MyoWare";
#endif

const uint8_t RAW_PIN = 36;
const uint8_t ENV_PIN = 39;
const uint8_t LED_PIN = 13;
const unsigned long SAMPLE_US = 1000;  // 1 kHz
const uint8_t IMU_EVERY = 5;           // 1 kHz / 5 = 200 Hz
const uint32_t STATUS_EVERY_MS = 5000;

#if USE_IMU
const int SDA_PIN = 21;  // ESP32 default I2C pins; change if the shield routes them elsewhere
const int SCL_PIN = 22;
const uint8_t MPU_ADDR = 0x68;
bool imuOk = false;
#endif

// ---- counters (core 1 only, except the link ones noted) ----
uint32_t samples = 0;       // E lines made
uint32_t skipped = 0;       // sample slots skipped after a stall (the receiver sees the gap in micros)
uint32_t lastStatusMs = 0;
uint32_t ratePrevSamples = 0, ratePrevMs = 0;

#if WIFI_LINK
enum LinkState : uint8_t { LINK_JOINING, LINK_UP, LINK_STREAMING };
// Shared with the Wi-Fi link task (core 0). Every value has a single writer.
StreamBufferHandle_t linkOut = nullptr;  // whole lines for the client: written by loop(), read by the link task
TaskHandle_t linkTaskHandle = nullptr;
volatile bool linkClient = false;        // link task: a client is connected and gets the lines
volatile bool linkHello = false;         // set by the link task, cleared by loop(): send header + status now
volatile uint8_t linkState = LINK_JOINING;
volatile uint32_t linkIp = 0;            // IPv4 in IPAddress byte order; 0 = not joined
volatile int8_t linkRssi = 0;            // dBm
volatile uint32_t linkClients = 0;       // clients accepted since boot
volatile uint32_t linkSendFails = 0;     // clients dropped after a failed send
volatile uint32_t linkStallMs = 0;       // link task: longest wait in one send during its last 5-s window
uint32_t linkDropped = 0;                // core 1: lines not sent because the buffer was full
uint32_t linkBufMax = 0;                 // core 1: most bytes waiting in linkOut since the last status line

const char *linkStateName(uint8_t s) {
  switch (s) {
    case LINK_UP: return "up";
    case LINK_STREAMING: return "streaming";
    default: return "joining";
  }
}
#endif

// ---- output: USB in batches (and Bluetooth when WIFI_LINK 0); a copy of every whole line for the Wi-Fi client ----
char batch[2048];
size_t batchLen = 0;
unsigned long lastSendUs = 0;
unsigned long nextSampleUs = 0;
uint8_t tick = 0;
bool hadClient = false;

void sendBatch() {
  if (batchLen == 0) return;
  Serial.write((const uint8_t *)batch, batchLen);
#if !WIFI_LINK
  if (SerialBT.hasClient()) SerialBT.write((const uint8_t *)batch, batchLen);
#endif
  batchLen = 0;
  lastSendUs = micros();
}

void addLine(const char *line) {
  const size_t n = strlen(line);
  if (batchLen + n + 1 > sizeof(batch)) sendBatch();
  char *dst = batch + batchLen;
  memcpy(dst, line, n);
  dst[n] = '\n';
  batchLen += n + 1;
#if WIFI_LINK
  // Only loop() (core 1) adds lines, so linkOut has one writer and one reader, as a FreeRTOS stream buffer needs.
  // One send per whole line (newline included), so the reader sees all of it or none of it; a line that doesn't
  // fit is dropped whole and counted: the client never gets half a line.
  if (linkClient && linkOut) {
    if (xStreamBufferSpacesAvailable(linkOut) >= n + 1) {
      xStreamBufferSend(linkOut, dst, n + 1, 0);
      const uint32_t waiting = LINK_BUF_BYTES - xStreamBufferSpacesAvailable(linkOut);
      if (waiting > linkBufMax) linkBufMax = waiting;
    } else {
      linkDropped++;
    }
  }
#endif
}

void sayHello() {
  char buf[200];
  snprintf(buf, sizeof(buf), "# truerehab-record v2 emg_hz=1000 raw_pin=%d env_pin=%d imu=%s link=%s",
           RAW_PIN, ENV_PIN,
#if USE_IMU
           imuOk ? "mpu6050_200hz" : "not_found",
#else
           "off",
#endif
#if WIFI_LINK
           "wifi:3334"
#else
           "bluetooth"
#endif
  );
  addLine(buf);
  addLine("# E,micros,raw,env | I,micros,ax,ay,az,gx,gy,gz");
}

// "# status ..." every 5 s: the recorder and model/check_session.py read these counters.
void sayStatus() {
  const uint32_t now = millis();
  const float hz = now > ratePrevMs ? 1000.0f * (samples - ratePrevSamples) / (now - ratePrevMs) : 0.0f;
  ratePrevSamples = samples;
  ratePrevMs = now;
  char buf[320];
  int n = snprintf(buf, sizeof(buf), "# status up_s=%lu emg_hz=%.1f samples=%lu skipped=%lu",
                   (unsigned long)(now / 1000), hz, (unsigned long)samples, (unsigned long)skipped);
#if WIFI_LINK
  const IPAddress ip((uint32_t)linkIp);
  // link_stall_ms: the longest single send of the last ~5 s (the network took nothing for that long).
  // link_buf_max: the most bytes waiting since the last status line (65536 = full: lines get dropped).
  snprintf(buf + n, sizeof(buf) - n,
           " wifi=%s ip=%u.%u.%u.%u rssi_dbm=%d link_clients=%lu link_dropped=%lu link_send_fails=%lu"
           " link_stall_ms=%lu link_buf_max=%lu",
           linkStateName(linkState), ip[0], ip[1], ip[2], ip[3], (int)linkRssi, (unsigned long)linkClients,
           (unsigned long)linkDropped, (unsigned long)linkSendFails, (unsigned long)linkStallMs,
           (unsigned long)linkBufMax);
  linkBufMax = 0;
#else
  snprintf(buf + n, sizeof(buf) - n, " bluetooth=%s", SerialBT.hasClient() ? "connected" : "waiting");
#endif
  addLine(buf);
}

#if USE_IMU
void imuWrite(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

bool imuBegin() {
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(400000);
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x75);  // WHO_AM_I
  if (Wire.endTransmission(false) != 0) return false;
  Wire.requestFrom(MPU_ADDR, (uint8_t)1);
  if (!Wire.available()) return false;
  // 0x68 = MPU-6050. Many "MPU-6050" boards carry an MPU-6500-family chip instead (0x70, 0x72,
  // 0x74, ...; the project's IMU board reads 0x74) with the same registers for everything used here.
  const uint8_t id = Wire.read();
  if (id == 0x00 || id == 0xFF) return false;
  imuWrite(0x6B, 0x00);  // wake up
  imuWrite(0x1A, 0x03);  // low-pass ~44 Hz
  imuWrite(0x1B, 0x00);  // gyro +-250 deg/s
  imuWrite(0x1C, 0x00);  // accel +-2 g
  if (id != 0x68) imuWrite(0x1D, 0x03);  // 6500 family: accel low-pass ~45 Hz is in ACCEL_CONFIG2
  return true;
}

void imuRead(unsigned long t) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);  // ACCEL_XOUT_H: ax ay az temp gx gy gz, big-endian int16
  if (Wire.endTransmission(false) != 0) return;
  if (Wire.requestFrom(MPU_ADDR, (uint8_t)14) != 14) return;
  int16_t v[7];
  for (int i = 0; i < 7; i++) v[i] = (int16_t)((Wire.read() << 8) | Wire.read());
  char buf[96];
  snprintf(buf, sizeof(buf), "I,%lu,%d,%d,%d,%d,%d,%d", t, v[0], v[1], v[2], v[4], v[5], v[6]);
  addLine(buf);
}
#endif

#if WIFI_LINK
// ============================================================================
// Wi-Fi link task (core 0): joins Wi-Fi, serves one TCP client and sends it the lines loop() queued.
// Only this task ever waits for the network; the 1-kHz sampling loop on core 1 never does.
// ============================================================================
WiFiServer linkServer(LINK_PORT);

void linkDiscard() {  // only from the link task (linkOut's single reader)
  static uint8_t junk[256];
  while (xStreamBufferReceive(linkOut, junk, sizeof junk, 0) > 0) {
  }
}

void linkTask(void *) {
  WiFi.setHostname(LINK_HOSTNAME);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);  // Wi-Fi power save holds packets back for 100+ ms
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  uint32_t joinStartMs = millis(), lastRssiMs = 0;
  uint32_t stallWindowMs = millis(), stallMax = 0;  // the longest send of the current 5-s window
  bool serving = false;
  WiFiClient client;
  static uint8_t chunk[1460];  // one TCP segment
  for (;;) {
    const uint32_t now = millis();
    if (WiFi.status() != WL_CONNECTED) {
      if (linkClient) {
        linkClient = false;
        client.stop();
      }
      linkIp = 0;
      linkState = LINK_JOINING;
      linkDiscard();
      if (now - joinStartMs >= LINK_REJOIN_MS) {  // still not joined (e.g. the network was off at boot): try again
        joinStartMs = now;
        WiFi.disconnect();
        WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
      }
      vTaskDelay(pdMS_TO_TICKS(100));
      continue;
    }
    joinStartMs = now;
    if (!serving) {  // first join: the server and the .local name then stay up across Wi-Fi drops
      linkServer.begin();
      linkServer.setNoDelay(true);
      MDNS.begin(LINK_HOSTNAME);
      MDNS.addService("truerehab-emg", "tcp", LINK_PORT);  // service names are 15 characters at most
      serving = true;
    }
    linkIp = (uint32_t)WiFi.localIP();
    if (now - lastRssiMs >= 1000) {
      lastRssiMs = now;
      linkRssi = (int8_t)WiFi.RSSI();
    }

    WiFiClient incoming = linkServer.accept();
    if (incoming) {  // a new client replaces the old one (e.g. the recorder reconnecting after a drop)
      linkClient = false;
      client.stop();
      client = incoming;
      client.setNoDelay(true);
      // Mark our packets CS4: Wi-Fi sends them in its "video" queue, ahead of ordinary traffic such as a dashboard
      // stream, and still in aggregates ("voice" would send each packet alone).
      const int tos = 0x80;
      client.setSocketOption(IPPROTO_IP, IP_TOS, &tos, sizeof(tos));
      linkDiscard();  // nothing from before this client
      linkClients = linkClients + 1;
      linkClient = true;
      linkHello = true;
    } else if (linkClient && !client.connected()) {
      linkClient = false;
      client.stop();
    }
    linkState = linkClient ? LINK_STREAMING : LINK_UP;
    if (!linkClient) {
      linkDiscard();
      vTaskDelay(pdMS_TO_TICKS(20));
      continue;
    }
    while (client.available() > 0 && client.read() >= 0) {
    }  // nothing to read from the client: drop anything it sends
    // Send about every 20 ms (~50 packets/s of ~0.5 KB at 1 kHz); a backlog of a full segment or more goes at once.
    if (xStreamBufferBytesAvailable(linkOut) < sizeof chunk) vTaskDelay(pdMS_TO_TICKS(20));
    const size_t n = xStreamBufferReceive(linkOut, chunk, sizeof chunk, 0);
    const uint32_t sendStartMs = millis();
    if (n > 0 && client.write(chunk, n) != n) {  // the client closed, or took nothing for ~10 s
      linkClient = false;
      client.stop();
      linkSendFails = linkSendFails + 1;
    }
    // A send waits when the network stops taking data (no acknowledgements): the board's view of a Wi-Fi pause.
    const uint32_t sendMs = millis() - sendStartMs;
    if (sendMs > stallMax) stallMax = sendMs;
    if (millis() - stallWindowMs >= 5000) {
      linkStallMs = stallMax;
      stallMax = 0;
      stallWindowMs = millis();
    }
  }
}
#endif

void setup() {
  Serial.begin(921600);
  pinMode(LED_PIN, OUTPUT);
  analogReadResolution(12);  // 0-4095
#if WIFI_LINK
  linkOut = xStreamBufferCreate(LINK_BUF_BYTES, 1);  // the link task polls it every 20 ms (no blocking reads)
  if (linkOut) {
    xTaskCreatePinnedToCore(linkTask, "link", 8192, nullptr, 2, &linkTaskHandle, 0);  // core 0, with Wi-Fi
  }
#else
  SerialBT.begin(BT_NAME);
#endif
#if USE_IMU
  imuOk = imuBegin();
#endif
  sayHello();
#if WIFI_LINK
  addLine(linkOut ? "# wifi link: tcp port 3334 at truerehab-myoware.local, one client at a time"
                  : "# wifi link: NOT started (no memory for its buffer)");
#endif
  ratePrevMs = millis();
  nextSampleUs = micros();
}

void loop() {
  while ((long)(micros() - nextSampleUs) < 0) {}
  unsigned long t = nextSampleUs;
  nextSampleUs += SAMPLE_US;
  // If something stalled us, restart the clock instead of bursting; the receiver sees the gap in micros.
  if ((long)(micros() - nextSampleUs) > (long)(10 * SAMPLE_US)) {
    skipped += (micros() - nextSampleUs) / SAMPLE_US;
    nextSampleUs = micros();
  }

  int raw = analogRead(RAW_PIN);
  int env = analogRead(ENV_PIN);
  char buf[48];
  snprintf(buf, sizeof(buf), "E,%lu,%d,%d", t, raw, env);
  addLine(buf);
  samples++;

#if USE_IMU
  if (imuOk && ++tick >= IMU_EVERY) {
    tick = 0;
    imuRead(t);
  }
#endif

#if WIFI_LINK
  bool client = linkClient;
  if (linkHello) {  // a Wi-Fi client just connected: tell it what's coming now, not at the next status
    linkHello = false;
    sayHello();
    sayStatus();
  }
#else
  bool client = SerialBT.hasClient();
  if (client && !hadClient) sayHello();  // the recorder just connected: tell it what's coming
#endif
  hadClient = client;
  digitalWrite(LED_PIN, client ? HIGH : LOW);

  if (millis() - lastStatusMs >= STATUS_EVERY_MS) {
    lastStatusMs = millis();
    sayStatus();
  }
  if (micros() - lastSendUs > 20000) sendBatch();  // USB at least every 20 ms
}
