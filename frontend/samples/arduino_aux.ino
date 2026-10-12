// Example Arduino sketch for the Web Serial input (USB serial source).
// Prints one line per sample as key:value pairs; the dashboard plots each key as an aux channel.
// Pins and scaling are placeholders: wire up your own sEMG / load-cell front end.

const int EMG_PIN = A0;
const int FORCE_PIN = A1;

void setup() {
  Serial.begin(115200);
}

void loop() {
  int emg = analogRead(EMG_PIN);
  int force = analogRead(FORCE_PIN);
  Serial.print("emg_raw:");
  Serial.print(emg);
  Serial.print(",force_raw:");
  Serial.println(force);
  delay(10); // ~100 Hz
}
