/* The image only drives the components; the global variables belong to DDD. */
void sensor_hub_step(void);
void controller_step(void);
void user_interface_step(void);
void event_logger_step(void);

int main(void)
{
    sensor_hub_step();
    controller_step();
    user_interface_step();
    event_logger_step();
    return 0;
}
