#include "HX711.h"
#define DT 2
#define SCK 3
#define BOTON_TARE 4

HX711 scale;
 
//float factor = 7100.0;  // Cambiar tras calibrar
float factor = 8658.36;  // Factor calibrado con 7.265kg

unsigned long t0;
bool tareSolicitado = false;

void setup() {
  Serial.begin(9600);
  pinMode(BOTON_TARE, INPUT_PULLUP);  // Botón entre D4 y GND
  scale.begin(DT, SCK);
  scale.set_gain(128);  // Canal A
  scale.set_scale(factor);
  scale.tare();         // Cero inicial
  t0 = millis();
  Serial.println("Tiempo_ms,Fuerza_kg");  // Encabezado CSV
}

void loop() {
  // Verificar si se presionó el botón de tare
  if (digitalRead(BOTON_TARE) == LOW && !tareSolicitado) {
    tareSolicitado = true;
    Serial.println(">>> TARE solicitado");
    scale.tare();
    delay(500); // Antirebote simple
  } else if (digitalRead(BOTON_TARE) == HIGH) {
    tareSolicitado = false;
  }

  // Si hay datos listos, leer y enviar
  if (scale.is_ready()) {
    unsigned long t = millis() - t0;
    float kg = scale.get_units(1);  // Leer una muestra
    Serial.print(t);
    Serial.print(",");
    Serial.println(kg, 4);  // Cuatro decimales
  }
}
