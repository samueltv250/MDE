#include <Arduino.h>



int azimuthMin = 10;    // Default value
int azimuthMax = 629;   // Default value
int elevationMin = 10;  // Default value
int elevationMax = 694; // Default value



// Define pins
const int pinUp = 10;  // Adjust pins as per our setup
const int pinDown = 11;
const int pinLeft = 12;
const int pinRight = 13;
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
  currentElevation = readElevation();
  currentAzimuth = readAzimuth();  // Update position after movement
  }

void loop() {
    digitalWrite(pinRight, HIGH);
    delay(100); // Delay will be the amount of time it takes to move 1 degree or 1 step
    digitalWrite(pinRight, LOW);
    
  if (Serial.available() > 0) {

    String command = Serial.readString();
    if (command.startsWith("calibrate")) {

      calibrate();
    } else {
      int separatorIndex = command.indexOf(',');
      if (separatorIndex != -1) {
        int desiredAzimuth = command.substring(5, separatorIndex).toInt();
        int desiredElevation = command.substring(separatorIndex + 1).toInt();
        moveMount(desiredAzimuth, desiredElevation);
      }
    }

  }
}

void calibrate() {

  digitalWrite(pinLeft, HIGH);
  delay(80000);
  digitalWrite(pinLeft, LOW);
  azimuthMin = min(azimuthMin, analogRead(pinStatusAzimuth));



  digitalWrite(pinRight, HIGH);
  delay(80000);
  digitalWrite(pinRight, LOW);
  azimuthMax = max(azimuthMax, analogRead(pinStatusAzimuth));



  digitalWrite(pinUp, HIGH);
  delay(80000);
  digitalWrite(pinUp, LOW);
  elevationMax = max(elevationMax, analogRead(pinStatusElevation));


  digitalWrite(pinDown, HIGH);
  delay(80000);
  digitalWrite(pinDown, LOW);
  elevationMin = min(elevationMin, analogRead(pinStatusElevation));

  Serial.print("Azimuth Min: ");
  Serial.print(azimuthMin);
  Serial.print(", Azimuth Max: ");
  Serial.print(azimuthMax);
  Serial.print(", Elevation Min: ");
  Serial.print(elevationMin);
  Serial.print(", Elevation Max: ");
  Serial.println(elevationMax);
}

void moveMount(int desiredAzimuth, int desiredElevation) {
  
  // For Azimuth
  while (currentAzimuth < desiredAzimuth) {
    digitalWrite(pinRight, HIGH);
    delay(100); // Delay will be the amount of time it takes to move 1 degree or 1 step
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
  Serial.println("Moved");

}

int readAzimuth() {
  int value = analogRead(pinStatusAzimuth);
  int azimuth = map(value, azimuthMin, azimuthMax, 0, 450);
  Serial.print("Azimuth: ");
  Serial.println(azimuth);
  return azimuth;
}

int readElevation() {
  int value = analogRead(pinStatusElevation);
  int elevation = map(value, elevationMin, elevationMax, 0, 180);
  Serial.print("Elevation: ");
  Serial.println(elevation);
  return elevation;
}