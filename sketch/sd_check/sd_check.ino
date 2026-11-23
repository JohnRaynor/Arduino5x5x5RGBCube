/*
  sd_check - does the SD module work at all?

  A standalone test with no FastLED, no cube and no protocol, so a result here
  is about the card and its wiring and nothing else. Flash it, open the Serial
  Monitor at 115200, and read the report.

  Wiring it assumes (the same as rgb_cube.ino):
      CS   D3        MOSI D11      MISO D12      SCK  D13
      VCC  5V        GND  GND
  The common blue module has its own regulator and level shifters and wants
  5 V. A bare micro-SD breakout is 3.3 V only and needs level shifting.
*/
#include <SPI.h>
#include <SdFat.h>

#define SD_CS_PIN 3

SdFat32 sd;
File32 entry;
File32 root;

void report(uint8_t mhz) {
  Serial.print(F("  "));
  Serial.print(mhz);
  Serial.print(F(" MHz: "));
  if (sd.begin(SdSpiConfig(SD_CS_PIN, SHARED_SPI, SD_SCK_MHZ(mhz)))) {
    Serial.println(F("OK"));
  } else {
    Serial.print(F("failed, code 0x"));
    Serial.print(sd.card()->errorCode(), HEX);
    Serial.print(F(" data 0x"));
    Serial.println(sd.card()->errorData(), HEX);
  }
}

void setup() {
  Serial.begin(115200);
  while (!Serial) {}
  delay(200);

  Serial.println();
  Serial.println(F("--- SD check ---"));
  Serial.print(F("chip select pin D"));
  Serial.println(SD_CS_PIN);

  pinMode(SD_CS_PIN, OUTPUT);

  // Slowest first: if 1 MHz works and 8 does not, the wiring is too long or
  // too noisy for the faster clock rather than the card being faulty.
  Serial.println(F("begin() at each clock:"));
  report(1);
  report(4);
  report(8);

  Serial.println(F("settling on 1 MHz for the rest of the test"));
  if (!sd.begin(SdSpiConfig(SD_CS_PIN, SHARED_SPI, SD_SCK_MHZ(1)))) {
    Serial.println(F("No card at any speed. Check, in this order:"));
    Serial.println(F("  1. the card is pushed fully home"));
    Serial.println(F("  2. VCC is on 5V, not 3V3, for a module with a regulator"));
    Serial.println(F("  3. CS really is on D3, and MOSI/MISO/SCK on D11/D12/D13"));
    Serial.println(F("  4. GND is shared"));
    Serial.println(F("  5. the card is FAT16 or FAT32, 32 GB or smaller"));
    return;
  }

  Serial.print(F("card size: "));
  Serial.print(sd.card()->sectorCount() / 2048);
  Serial.println(F(" MB"));
  Serial.print(F("FAT type: FAT"));
  Serial.println(sd.vol()->fatType());

  Serial.println(F("files in the root directory:"));
  uint16_t count = 0;
  if (root.open("/")) {
    while (entry.openNext(&root, O_RDONLY)) {
      if (!entry.isDir()) {
        Serial.print(F("  "));
        entry.printName(&Serial);
        Serial.print(F("  "));
        Serial.print(entry.fileSize());
        Serial.print(F(" bytes"));
        // A pattern file is a whole number of 377-byte frames.
        if (entry.fileSize() % 377 == 0 && entry.fileSize() > 0) {
          Serial.print(F("  = "));
          Serial.print(entry.fileSize() / 377);
          Serial.print(F(" frames"));
        }
        Serial.println();
        count++;
      }
      entry.close();
    }
    root.close();
  }
  Serial.print(count);
  Serial.println(F(" file(s)"));

  Serial.println(F("--- reading every file right through ---"));
  if (root.open("/")) {
    while (entry.openNext(&root, O_RDONLY)) {
      if (!entry.isDir()) {
        uint32_t read = 0;
        uint8_t buffer[64];
        int got;
        while ((got = entry.read(buffer, sizeof(buffer))) > 0) read += got;
        Serial.print(F("  "));
        entry.printName(&Serial);
        Serial.print(got < 0 ? F("  READ ERROR after ") : F("  read "));
        Serial.print(read);
        Serial.println(F(" bytes"));
      }
      entry.close();
    }
    root.close();
  }
  Serial.println(F("--- done ---"));
}

void loop() {}
