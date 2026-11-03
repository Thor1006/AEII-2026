/*
  MyoWare 2.0 Wireless Shield demo - live muscle activity in the Arduino IDE.

  Hardware: MyoWare 2.0 Muscle Sensor + MyoWare 2.0 Wireless Shield
  (ESP32-WROOM, CH340 USB-C). The shield reads the sensor through its pogo pins:
    ENV -> GPIO39 / A3   (used here)
    RAW -> GPIO36 / A4
    REF -> GPIO35 / A5
  Arduino IDE: install the "esp32" boards package (Espressif), select
  "ESP32 Dev Module", and the CH340 port.

  SAFETY (SparkFun's warning): do not have the shield on a person while USB-C
  is plugged in (programming or charging). For live data on a person, unplug
  USB, run on the battery, and read the data over Bluetooth (see below).

  Viewing the data:
    - Bench (no person): USB port -> Tools > Serial Plotter, 115200 baud.
    - On a person: pair your computer with "TrueRehab-MyoWare", then pick its
      Bluetooth serial port in the Arduino IDE and open the Serial Plotter.

  Use:
    1. Keep the muscle relaxed for the first 3 s (calibration, LED 13 blinks).
    2. Flex: Smooth rises above Threshold and LED 13 turns on.

  Commands (type in the plotter/monitor input box and press Enter):
    c  recalibrate (relax for 3 s)
    m  switch between plotter view and text view (use text view in Serial Monitor)
*/

#define USE_BLUETOOTH 1  // Bluetooth Classic serial port; set 0 for USB only

#if USE_BLUETOOTH
#include "BluetoothSerial.h"
BluetoothSerial SerialBT;
const char *BT_NAME = "TrueRehab-MyoWare";
#endif

const uint8_t ENV_PIN = A3;  // GPIO39 on the Wireless Shield
const uint8_t LED_PIN = 13;  // general-purpose LED on the shield

const unsigned long SAMPLE_US = 1000;  // 1 kHz sampling
const uint8_t PLOT_EVERY = 20;         // 1 kHz / 20 = 50 lines/s to the plotter
const uint16_t TEXT_EVERY = 200;       // 5 lines/s in text view
const float SMOOTH_ALPHA = 0.05;       // moving average, ~20 ms at 1 kHz
const unsigned long CAL_MS = 3000;
const float THRESH_SIGMAS = 5.0;       // threshold = baseline + 5 x resting noise...
const float THRESH_MIN = 80.0;         // ...but at least 80 ADC counts (of 4095) above baseline
const unsigned long MIN_REP_MS = 150;  // shorter bursts are twitches, not contractions

// Sends everything to USB serial and, when a device is connected, to Bluetooth.
class DualOut : public Print {
 public:
  size_t write(uint8_t b) override { return write(&b, 1); }
  size_t write(const uint8_t *buf, size_t len) override {
    Serial.write(buf, len);
#if USE_BLUETOOTH
    if (SerialBT.hasClient()) SerialBT.write(buf, len);
#endif
    return len;
  }
} out;

float baseline = 0, threshold = 0, release = 0;
float smooth = 0, peak = 0;
bool active = false, textView = false;
unsigned long activeSince = 0;
unsigned int reps = 0;
unsigned long nextSampleUs = 0;
uint16_t tick = 0;

void setLed(bool on) {
  digitalWrite(LED_PIN, on ? HIGH : LOW);
}

void waitForNextSample() {
  while ((long)(micros() - nextSampleUs) < 0) {}
  nextSampleUs += SAMPLE_US;
  // If printing stalled us for a while, restart the clock instead of bursting.
  if ((long)(micros() - nextSampleUs) > (long)(10 * SAMPLE_US)) nextSampleUs = micros();
}

int readEnv() {
  int env = analogRead(ENV_PIN);
  smooth += SMOOTH_ALPHA * (env - smooth);
  return env;
}

void plotLine(int env) {
  // "Label:value,Label:value" -> one named line per value in the Serial Plotter
  char buf[80];
  snprintf(buf, sizeof(buf), "ENV:%d,Smooth:%d,Baseline:%d,Threshold:%d",
           env, (int)smooth, (int)baseline, (int)threshold);
  out.println(buf);
}

int effortPercent() {
  float pct = (smooth - baseline) / (peak - baseline) * 100.0;
  return (int)constrain(pct, 0.0, 100.0);
}

void textLine(int env) {
  char buf[80];
  snprintf(buf, sizeof(buf), "env %4d  smooth %4d  effort %3d%%  reps %u  %s",
           env, (int)smooth, effortPercent(), reps, active ? "ACTIVE" : "-");
  out.println(buf);
}

void calibrate() {
  if (textView) out.println("Calibrating - relax the muscle for 3 s");
  baseline = threshold = 0;
  smooth = analogRead(ENV_PIN);

  // Running mean and variance of the relaxed signal (Welford's method)
  unsigned long n = 0;
  float mean = 0, m2 = 0;
  unsigned long start = millis();
  while (millis() - start < CAL_MS) {
    waitForNextSample();
    int env = readEnv();
    n++;
    float d = smooth - mean;
    mean += d / n;
    m2 += d * (smooth - mean);
    setLed((millis() / 100) % 2);
    if (!textView && n % PLOT_EVERY == 0) plotLine(env);
  }

  float noise = sqrt(m2 / n);
  baseline = mean;
  threshold = baseline + max(THRESH_SIGMAS * noise, THRESH_MIN);
  release = baseline + 0.6 * (threshold - baseline);  // hysteresis: no flicker at the edge
  peak = threshold;
  active = false;
  reps = 0;
  tick = 0;
  setLed(false);

  if (textView) {
    char buf[80];
    snprintf(buf, sizeof(buf), "Baseline %d, noise %d, threshold %d - go!",
             (int)baseline, (int)noise, (int)threshold);
    out.println(buf);
  }
}

void updateActivation() {
  unsigned long now = millis();
  if (!active && smooth > threshold) {
    active = true;
    activeSince = now;
  } else if (active && smooth < release) {
    active = false;
    unsigned long held = now - activeSince;
    if (held >= MIN_REP_MS) {
      reps++;
      if (textView) {
        char buf[60];
        snprintf(buf, sizeof(buf), ">> contraction %u: %lu ms", reps, held);
        out.println(buf);
      }
    }
  }
  setLed(active);
}

void handleCommand(char c) {
  if (c == 'c' || c == 'C') {
    calibrate();
  } else if (c == 'm' || c == 'M') {
    textView = !textView;
    tick = 0;
    if (textView) out.println("Text view - send m for plotter view, c to recalibrate");
  }
}

void handleCommands() {
  while (Serial.available()) handleCommand(Serial.read());
#if USE_BLUETOOTH
  while (SerialBT.available()) handleCommand(SerialBT.read());
#endif
}

void setup() {
  Serial.begin(115200);
#if USE_BLUETOOTH
  SerialBT.begin(BT_NAME);
#endif
  pinMode(LED_PIN, OUTPUT);
  analogReadResolution(12);  // 0-4095
  nextSampleUs = micros();
  calibrate();
}

void loop() {
  handleCommands();
  waitForNextSample();
  int env = readEnv();
  if (smooth > peak) peak = smooth;
  updateActivation();

  tick++;
  if (textView && tick >= TEXT_EVERY) {
    tick = 0;
    textLine(env);
  } else if (!textView && tick >= PLOT_EVERY) {
    tick = 0;
    plotLine(env);
  }
}
