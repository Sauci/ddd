#include "Controller.h"

void controller_step(void);

void controller_step(void)
{
    ValueE = (uint16_t)(ValueA * 16U);  /* reads an input, writes an output */
    ValueF = -100;
    StateA = (uint8_t)STATE_ACTIVE;     /* the enum comes from ddd_types.h */
    ValueH = (int16_t)(MapA[0][0] + CurveA[0] + AxisA[0] + ParameterA);
}
