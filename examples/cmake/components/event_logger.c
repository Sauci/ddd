#include "EventLogger.h"

void event_logger_step(void);

void event_logger_step(void)
{
    ValueK[0][0] = FlagA ? (int8_t)0 : (int8_t)1;
    ValueJ = (uint8_t)(ValueI & 0xFFU);
}
