/*
 * Stands in for a header DDD does not generate and does not read: the sensor vendor's own.
 * SensorHub declares DriverState_t as an external type naming this file, so DDD writes the
 * include line into ddd_types.h and leaves the type itself alone - it has no datatype, no
 * unit, no conversion and no a2l record, because DDD does not know its layout.
 */
#ifndef SENSOR_HUB_DRIVER_H
#define SENSOR_HUB_DRIVER_H

#include <stdint.h>

typedef struct
{
    uint16_t revision; /* the driver's own version word */
    uint8_t faults;    /* a bitmask the vendor's diagnosis code decodes */
} DriverState_t;

#endif /* SENSOR_HUB_DRIVER_H */
