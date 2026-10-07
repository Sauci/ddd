/*
 * Engine.h
 *
 * Global variable data dictionary of project 'AddressFixture'.
 * Generated from 'project.ddd.json' by ddd 0.11.0.
 *
 * DO NOT EDIT - every change is lost the next time DDD runs.
 */
/*
 * Interface of software component 'Engine'.
 *
 * Owns one variable of every shape the address fixtures place
 *
 * Only the variables declared in the DDD description of this component are
 * visible here; everything else is intentionally out of reach.
 */
#ifndef DDD_COMPONENT_ENGINE_H
#define DDD_COMPONENT_ENGINE_H

#include "ddd_types.h"

/* locals - owned exclusively by Engine */
/** Shaft speed [rpm] */
extern volatile uint16_t Speed;
/** Shaft torque, initialised so that it lands in .data [Nm] */
extern int32_t Torque;
/** Gear ratio */
extern float Ratio;
/** Energy spent since the last reset [J] */
extern double Energy;
/** Timer ticks since the last reset */
extern volatile uint64_t Ticks;
/** Engaged gear, negative in reverse */
extern int8_t Gear;
/** The last eight raw samples, an array of values */
extern uint8_t Samples[8];
/** Whether the engine may start (calibration parameter) */
extern const bool Enabled;
/** Speed loop gain (calibration parameter) */
extern const volatile float Gain;
/** Torque limit [Nm] (calibration parameter) */
extern const int16_t Limit;
/** Four calibratable thresholds (calibration value block) */
extern const uint16_t Table[4];
/** The inlet sensor: a structure nesting another, with arrays inside */
extern volatile Sensor_t Inlet;
/** An array of structures in one dimension */
extern Cell_t Cells[3];
/** An array of structures in two dimensions */
extern Cell_t Grid[2][3];
/** Bitfields of one, two and four bytes between values */
extern volatile Status_t Status;
/** Values inside a bitfield's unit, and an eight byte unit */
extern Mixed_t Mixed;
/** The calibration of the speed loop, bitfields among its values */
extern const volatile Tuning_t Tuning;

#endif /* DDD_COMPONENT_ENGINE_H */
