#include <Arduino.h>

// Define pins
const int pinUp = 2;  // Adjust pins as per our setup
const int pinDown = 3;
const int pinLeft = 4;
const int pinRight = 5;
const int pinStatusAzimuth = A0;    // Analog pin for Azimuth feedback
const int pinStatusElevation = A1;  // Analog pin for Elevation feedback

// Variables for position
int currentAzimuth = 0;
int currentElevation = 0;

void setup() {
  Serial.begin(9600);
  
  pinMode(pinUp, OUTPUT);
  pinMode(pinDown, OUTPUT);
  pinMode(pinLeft, OUTPUT);
  pinMode(pinRight, OUTPUT);

  digitalWrite(pinUp, LOW);
  digitalWrite(pinDown, LOW);
  digitalWrite(pinLeft, LOW);
  digitalWrite(pinRight, LOW);
}

void loop() {
  if (Serial.available() > 0) {
    String command = Serial.readString();
    int separatorIndex = command.indexOf(',');
    if (separatorIndex != -1) {
      int desiredAzimuth = command.substring(5, separatorIndex).toInt();
      int desiredElevation = command.substring(separatorIndex + 1).toInt();
      moveMount(desiredAzimuth, desiredElevation);
    }
  }
}

void moveMount(int desiredAzimuth, int desiredElevation) {
  
  // For Azimuth
  while (currentAzimuth < desiredAzimuth) {
    digitalWrite(pinRight, HIGH);
    delay(100);
    digitalWrite(pinRight, LOW);
    currentAzimuth = readAzimuth();  // Update position after movement
  }
  
  while (currentAzimuth > desiredAzimuth) {
    digitalWrite(pinLeft, HIGH);
    delay(100);
    digitalWrite(pinLeft, LOW);
    currentAzimuth = readAzimuth();
  }

  // For Elevation
  while (currentElevation < desiredElevation) {
    digitalWrite(pinUp, HIGH);
    delay(100);
    digitalWrite(pinUp, LOW);
    currentElevation = readElevation();
  }
  
  while (currentElevation > desiredElevation) {
    digitalWrite(pinDown, HIGH);
    delay(100);
    digitalWrite(pinDown, LOW);
    currentElevation = readElevation();
  }
}

int readAzimuth() {
  // Convert voltage reading to azimuth
  int value = analogRead(pinStatusAzimuth); // Can only read up to 3.3 volts
  int azimuth = map(value, 0, 1023, 0, 450);  // Maps 0-1023 to 0-450
  return azimuth;
}

int readElevation() {
  // Convert voltage reading to elevation
  int value = analogRead(pinStatusElevation); // Can only read up to 3.3 volts
  int elevation = map(value, 0, 1023, 0, 180);  // Maps 0-1023 (0-3.3 Volts) to 0-180
  return elevation;
}
