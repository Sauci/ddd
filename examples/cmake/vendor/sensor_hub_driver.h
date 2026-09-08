/*
 * Stands in for a header DDD does not generate and does not read: the sensor vendor's own.
 * sensor_hub declares an external type naming it, so ddd_types.h includes it, and every
 * component that includes a generated header has to be able to find it - event_logger among
 * them, although event_logger does not link sensor_hub. That is what ddd_generate() arranges
 * when it hands the registered components the compile usage collected on <image>_ddd_headers.
 *
 * The #error is what makes the second half of that testable. A real vendor header would not
 * refuse to compile without its configuration flag; it would quietly lay DriverState_t out
 * differently, and the image would disagree with itself - the failure that compiles. Refusing
 * out loud is the same fault, made visible to the build.
 */
#ifndef SENSOR_HUB_DRIVER_H
#define SENSOR_HUB_DRIVER_H

#include <stdint.h>

#ifndef SENSOR_HUB_DRIVER_V2
#error "SENSOR_HUB_DRIVER_V2 is not defined. sensor_hub publishes it, and the layout below depends on it."
#endif

typedef struct
{
    uint16_t revision;
    uint8_t faults;
} DriverState_t;

#endif /* SENSOR_HUB_DRIVER_H */
