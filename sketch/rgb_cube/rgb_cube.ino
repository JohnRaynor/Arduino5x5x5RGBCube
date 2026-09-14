/*
  5x5x5 addressable RGB LED cube - Arduino Nano.

  Plays random pattern files from the SD card, and accepts patterns over USB
  serial from rgb_cube_editor.py: either previewed live or written to the SD
  card.  See ../../README.md for the file format and the serial protocol.

  Frame: 125 x (R, G, B) in LED chain order, then a 2-byte big-endian display
  time in ms - 377 bytes.  The chain order is defined by ledIndex() below and
  must match cube_layout.py on the PC.

  Serial protocol (115200 baud).  Every command is preceded by 64 zero bytes
  and starts with the ASCII bytes CUBE:
    CUBE P <frame>                     preview: display the frame for its time,
                                       then reply FRAME and hold it
    CUBE R                             resume random SD playback, reply RESUMED
    CUBE W <len> <name> <size LE32>    reply READY, then accept the file data in
                                       64-byte blocks, replying NEXT after each
                                       block and DONE after the last
    ERR <text>                         anything that failed

  Why the zero bytes: FastLED.show() turns interrupts off for ~3.8 ms and the
  UART holds only two bytes, so bytes arriving during a refresh are lost.  Any
  received byte stops refreshes for SERIAL_QUIET_MS; the leading zeros absorb
  the loss so the command itself arrives intact.

  Pins: LED data D6 (through 330 ohm), SD chip select D3, SD on hardware SPI.
*/
#include <FastLED.h>
#include <SPI.h>
#include <SdFat.h>

#define LED_TYPE        APA106     // PL9823 for those LEDs
#define COLOR_ORDER     RGB        // swap to GRB etc. if red and green are exchanged
#define DATA_PIN        6
#define SD_CS_PIN       3
#define NUM_LEDS        125
#define FRAME_BYTES     (NUM_LEDS * 3 + 2)
#define MAX_MILLIAMPS   4000       // software current cap; supply is 5 V 5 A
#define PREVIEW_HOLD_MS 60000UL    // resume random playback if the PC goes quiet
#define SERIAL_QUIET_MS 50         // no refreshes this long after any serial byte
#define SD_BLOCK        64         // bytes per NEXT acknowledgement during an SD write

CRGB leds[NUM_LEDS];
uint8_t *const frameBytes = (uint8_t *)leds;   // frames are received / read straight into leds[]

// RAM is tight on the Nano (each File32 costs ~85 bytes), so only two handles:
SdFat32 sd;
File32 playbackFile;   // the pattern being played; also the iterator while counting files
File32 scratchFile;    // the root directory while choosing a file; the destination during an SD write
bool sdOk = false;
uint16_t patternCount = 0;

unsigned long frameEnd = 0;        // random playback: when the current frame expires
unsigned long previewEnd = 0;      // preview: when the current frame has been shown long enough
unsigned long previewHoldEnd = 0;  // preview: when to give up waiting for the PC
unsigned long lastSerialByte = 0;
bool previewMode = false;          // holding a PC frame; random playback paused
bool previewPending = false;       // a preview frame has arrived and is waiting to be shown
bool previewWaiting = false;       // a preview frame is being displayed for its time
uint16_t previewTime = 0;
bool needShow = false;             // leds[] has changed and should be sent to the cube

enum ReceiveState { FIND_MAGIC, READ_COMMAND, READ_PREVIEW, READ_NAME_LENGTH, READ_NAME, READ_SIZE, READ_FILE };
ReceiveState receiveState = FIND_MAGIC;
uint8_t magicPosition = 0;
uint16_t receiveCount = 0;
uint8_t fileNameLength = 0;
char receivedName[13];
uint8_t sizeBytes[4];
uint32_t bytesRemaining = 0;

// ---------------------------------------------------------------- layout ----
// x: left-right, y: front-back, z: bottom-top, all 0..4.  Same as cube_layout.py.
uint8_t ledIndex(uint8_t x, uint8_t y, uint8_t z) {
  if (z & 1) { x = 4 - x; y = 4 - y; }   // odd layers are stacked rotated 180 degrees
  uint8_t col = (y & 1) ? 4 - x : x;     // serpentine within the layer
  return z * 25 + y * 5 + col;
}

// ------------------------------------------------------------------ cube ----
void showIfQuiet() {
  // Refresh only when nothing has arrived on serial recently and no transfer is running.
  if (!needShow || receiveState == READ_FILE) return;
  if ((long)(millis() - lastSerialByte) < SERIAL_QUIET_MS) return;
  FastLED.show();
  needShow = false;
  if (previewPending) {              // the preview timer starts when the frame is visible
    previewPending = false;
    previewWaiting = true;
    previewEnd = millis() + previewTime;
  }
}

void serialError(const __FlashStringHelper *text) {
  Serial.print(F("ERR "));
  Serial.println(text);
}

// -------------------------------------------------------------- SD files ----
void countPatternFiles() {
  patternCount = 0;
  if (playbackFile.isOpen()) playbackFile.close();
  if (!sdOk || !scratchFile.open("/")) return;
  while (playbackFile.openNext(&scratchFile, O_RDONLY)) {
    if (!playbackFile.isDir()) patternCount++;
    playbackFile.close();
  }
  scratchFile.close();
}

void openRandomPattern() {
  if (playbackFile.isOpen()) playbackFile.close();
  if (!patternCount || !scratchFile.open("/")) return;
  uint16_t wanted = random(patternCount), index = 0;
  while (playbackFile.openNext(&scratchFile, O_RDONLY)) {
    if (!playbackFile.isDir() && index++ == wanted) break;
    playbackFile.close();
  }
  scratchFile.close();
}

void loadRandomFrame() {
  if (!playbackFile.isOpen() || playbackFile.available() < FRAME_BYTES) openRandomPattern();
  if (!playbackFile.isOpen() || playbackFile.available() < FRAME_BYTES) return;
  // The 375 colour bytes go straight into leds[]; the 2-byte time is read separately.
  uint8_t timeBytes[2];
  if (playbackFile.read(frameBytes, NUM_LEDS * 3) != NUM_LEDS * 3 || playbackFile.read(timeBytes, 2) != 2) {
    playbackFile.close();
    return;
  }
  frameEnd = millis() + ((uint16_t)timeBytes[0] << 8 | timeBytes[1]);
  needShow = true;
}

// ---------------------------------------------------------------- serial ----
void resetReceive() {
  receiveState = FIND_MAGIC;
  magicPosition = 0;
  receiveCount = 0;
}

void startPreviewFrame() {
  previewMode = true;          // stop random playback overwriting leds[] while the frame arrives
  previewWaiting = previewPending = false;
  receiveCount = 0;
  receiveState = READ_PREVIEW;
}

void finishFileTransfer() {
  if (scratchFile.close()) Serial.println(F("DONE"));   // close flushes SdFat's cache
  else serialError(F("SD write failed"));
  countPatternFiles();          // the new file joins the random rotation
  resetReceive();
}

void processReceivedByte(uint8_t value) {
  static const char magic[] = "CUBE";
  lastSerialByte = millis();

  switch (receiveState) {
    case FIND_MAGIC:
      magicPosition = (value == magic[magicPosition]) ? magicPosition + 1 : (value == 'C' ? 1 : 0);
      if (magicPosition == 4) receiveState = READ_COMMAND;
      break;

    case READ_COMMAND:
      if (value == 'P') startPreviewFrame();
      else if (value == 'W') { receiveState = READ_NAME_LENGTH; }
      else if (value == 'R') {
        previewMode = previewWaiting = previewPending = false;
        frameEnd = millis();
        Serial.println(F("RESUMED"));
        resetReceive();
      } else { serialError(F("unknown command")); resetReceive(); }
      break;

    case READ_PREVIEW: {
      // First 375 bytes are colours, straight into leds[]; last 2 are the time.
      static uint8_t timeBytes[2];
      if (receiveCount < NUM_LEDS * 3) frameBytes[receiveCount] = value;
      else timeBytes[receiveCount - NUM_LEDS * 3] = value;
      if (++receiveCount == FRAME_BYTES) {
        previewTime = (uint16_t)timeBytes[0] << 8 | timeBytes[1];
        previewPending = true;
        needShow = true;
        resetReceive();
      }
      break;
    }

    case READ_NAME_LENGTH:
      if (!value || value > 12) { serialError(F("bad filename")); resetReceive(); }
      else { fileNameLength = value; receiveCount = 0; receiveState = READ_NAME; }
      break;

    case READ_NAME:
      receivedName[receiveCount++] = value;
      if (receiveCount == fileNameLength) {
        receivedName[receiveCount] = 0;
        receiveCount = 0;
        receiveState = READ_SIZE;
      }
      break;

    case READ_SIZE:
      sizeBytes[receiveCount++] = value;
      if (receiveCount == 4) {
        bytesRemaining = (uint32_t)sizeBytes[0] | (uint32_t)sizeBytes[1] << 8 |
                         (uint32_t)sizeBytes[2] << 16 | (uint32_t)sizeBytes[3] << 24;
        if (!sdOk) { serialError(F("no SD card")); resetReceive(); }
        else if (bytesRemaining == 0 || bytesRemaining % FRAME_BYTES) { serialError(F("bad size")); resetReceive(); }
        else {
          if (playbackFile.isOpen()) playbackFile.close();   // playback pauses during the transfer
          if (!scratchFile.open(receivedName, O_WRONLY | O_CREAT | O_TRUNC)) { serialError(F("SD open failed")); resetReceive(); }
          else { receiveCount = 0; receiveState = READ_FILE; Serial.println(F("READY")); }
        }
      }
      break;

    case READ_FILE:
      if (scratchFile.write(value) != 1) {     // goes into SdFat's 512-byte cache
        scratchFile.close();
        serialError(F("SD write failed"));
        resetReceive();
        return;
      }
      bytesRemaining--;
      if (++receiveCount == SD_BLOCK) {
        receiveCount = 0;
        if (bytesRemaining) Serial.println(F("NEXT"));   // the PC sends the next block only now
      }
      if (!bytesRemaining) finishFileTransfer();
      break;
  }
}

// ------------------------------------------------------------------ main ----
void setup() {
  Serial.begin(115200);
  FastLED.addLeds<LED_TYPE, DATA_PIN, COLOR_ORDER>(leds, NUM_LEDS);
  FastLED.setMaxPowerInVoltsAndMilliamps(5, MAX_MILLIAMPS);
  FastLED.clear(true);

  pinMode(SD_CS_PIN, OUTPUT);
  sdOk = sd.begin(SdSpiConfig(SD_CS_PIN, SHARED_SPI, SD_SCK_MHZ(8)));
  if (!sdOk) serialError(F("SD initialisation failed"));   // previews still work
  randomSeed(analogRead(A0));
  countPatternFiles();
  Serial.println(F("READY"));
}

void loop() {
  while (Serial.available()) processReceivedByte(Serial.read());

  if (previewWaiting && (long)(millis() - previewEnd) >= 0) {
    previewWaiting = false;
    previewHoldEnd = millis() + PREVIEW_HOLD_MS;
    Serial.println(F("FRAME"));
  }
  if (previewMode && !previewWaiting && !previewPending && receiveState != READ_PREVIEW &&
      (long)(millis() - previewHoldEnd) >= 0) {
    previewMode = false;         // the PC went away; back to random playback
    frameEnd = millis();
  }
  if (!previewMode && receiveState != READ_FILE && (long)(millis() - frameEnd) >= 0) loadRandomFrame();

  showIfQuiet();
}
