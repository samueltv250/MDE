#include <Arduino.h>



int azimuthMin = 5;    // Default value
int azimuthMax = 627;   // Default value
int elevationMin = 7;  // Default value
int elevationMax = 697; // Default value
int numReadings = 10;  


// Define pins
const int pinUp = 10;  // Adjust pins as per our setup
const int pinDown = 11;
const int pinLeft = 12;
const int pinRight = 13;
const int pinStatusAzimuth = A0;  // Analog pin for Azimuth feedback
const int pinStatusElevation = A1;  // Analog pin for Elevation feedback

// Variables for position
float currentAzimuth = 0;
float currentElevation = 0;

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
  currentElevation = readElevation();
  currentAzimuth = readAzimuth();  // Update position after movement
  }

void loop() {
  if (Serial.available() > 0) {

    String command = Serial.readString();
    if (command.startsWith("calibrate")) {
      calibrate();
    } else {
      int separatorIndex = command.indexOf(',');
      if (separatorIndex != -1) {
      float desiredAzimuth = command.substring(5, separatorIndex).toFloat();
      float desiredElevation = command.substring(separatorIndex + 1).toFloat();
        moveMount(desiredAzimuth, desiredElevation);
      }
    }

  }
}
float get_readings(int pin){
  int sum = 0;
  for (int i = 0; i < numReadings; i++) {
    sum += analogRead(pin);
    delay(100); // short delay to stabilize the analog reading
  }
  return sum / numReadings;
}


void calibrate() {

  digitalWrite(pinLeft, HIGH);
  delay(80000);
  digitalWrite(pinLeft, LOW);


  azimuthMin = get_readings(pinStatusAzimuth);
  Serial.print("Azimuth Min: ");
  Serial.println(azimuthMin);

  digitalWrite(pinRight, HIGH);
  delay(80000);
  digitalWrite(pinRight, LOW);

  azimuthMax = get_readings(pinStatusAzimuth);


  Serial.print("Azimuth Max: ");
  Serial.println(azimuthMax);


  digitalWrite(pinUp, HIGH);
  delay(80000);
  digitalWrite(pinUp, LOW);

  elevationMax = get_readings(pinStatusElevation);

  Serial.print("Elevation Max: ");
  Serial.println(elevationMax);

  digitalWrite(pinDown, HIGH);
  delay(80000);
  digitalWrite(pinDown, LOW);
  
  elevationMin = get_readings(pinStatusElevation);
  Serial.print("Elevation Min: ");
  Serial.println(elevationMin);


  Serial.print("Azimuth Min: ");
  Serial.print(azimuthMin);
  Serial.print(", Azimuth Max: ");
  Serial.print(azimuthMax);
  Serial.print(", Elevation Min: ");
  Serial.print(elevationMin);
  Serial.print(", Elevation Max: ");
  Serial.println(elevationMax);
}

void moveMount(float desiredAzimuth, float desiredElevation) {
  const int stepDelay = 100;
  
  // For Azimuth
  while (fabs(currentAzimuth - desiredAzimuth) > 1) {
    if (currentAzimuth < desiredAzimuth) {
      digitalWrite(pinRight, HIGH);
      delay(stepDelay);
      digitalWrite(pinRight, LOW);
    } else {
      digitalWrite(pinLeft, HIGH);
      delay(stepDelay);
      digitalWrite(pinLeft, LOW);
    }
    currentAzimuth = readAzimuth(); // Update position after movement
  }
  
  // For Elevation
  while (fabs(currentElevation - desiredElevation) > 0.01) {
    if (currentElevation < desiredElevation) {
      digitalWrite(pinUp, HIGH);
      delay(stepDelay);
      digitalWrite(pinUp, LOW);
    } else {
      digitalWrite(pinDown, HIGH);
      delay(stepDelay);
      digitalWrite(pinDown, LOW);
    }
    currentElevation = readElevation();
  }
  Serial.println("Moved");
}

// The read functions now return float values and map to a float range
float readAzimuth() {
  int value = analogRead(pinStatusAzimuth);
  float azimuth = map(value, azimuthMin, azimuthMax, 0.0, 450.0);

  return azimuth;
}

float readElevation() {
  int value = analogRead(pinStatusElevation);
  float elevation = map(value, elevationMin, elevationMax, 0.0, 180.0);

  return elevation;
}