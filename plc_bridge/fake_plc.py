"""PLC de prueba: servidor Modbus TCP que imita al S7-1200 de la planta.

Sirve para probar el puente (bridge.py) sin el PLC real. Implementa el mismo
mapa de registros y la misma lógica de control que docs/PLC_VDF.md, con un
D700 "virtual" que acelera con rampa.

Uso (en la Raspberry o en tu PC):
    python fake_plc.py              # escucha en 0.0.0.0:5020
    PLC_HOST=127.0.0.1 PLC_PORT=5020 python bridge.py
"""
import logging
import os
import threading
import time

from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusSlaveContext
from pymodbus.server import StartTcpServer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("fake_plc")

PORT = int(os.environ.get("FAKE_PLC_PORT", "5020"))
TICK = 0.1
WATCHDOG_TIMEOUT = 5.0
AUTO_HYSTERESIS = 3.0
AUTO_KP = 4.0
AUTO_MIN_HZ = 20.0
MAX_HZ = 50.0
RAMP_HZ_PER_S = 10.0

holding = ModbusSequentialDataBlock(0, [0] * 20)
context = ModbusServerContext(slaves=ModbusSlaveContext(hr=holding, zero_mode=True), single=True)


def plc_cycle():
    # Valores iniciales de comando (como los "valores de arranque" del DB)
    holding.setValues(0, [1, 1, 700, 350])  # marcha, modo_auto, setpoint 70.0 %, velocidad 35.0 Hz
    marcha = 0
    frecuencia = 0.0
    last_watchdog = None
    last_watchdog_change = time.monotonic()
    while True:
        cmd_marcha, cmd_auto, sp_x10, vel_x10, nivel_x10, watchdog = holding.getValues(0, 6)
        now = time.monotonic()
        if watchdog != last_watchdog:
            last_watchdog, last_watchdog_change = watchdog, now
        comunicacion_ok = now - last_watchdog_change < WATCHDOG_TIMEOUT

        setpoint, nivel = sp_x10 / 10, nivel_x10 / 10
        if cmd_auto:
            if nivel >= setpoint:
                marcha = 0
            elif nivel < setpoint - AUTO_HYSTERESIS:
                marcha = 1
            target = max(AUTO_MIN_HZ, min(MAX_HZ, AUTO_KP * (setpoint - nivel)))
        else:
            marcha = 1 if cmd_marcha else 0
            target = vel_x10 / 10
        if not comunicacion_ok:
            marcha = 0
        target = target if marcha else 0.0
        step = RAMP_HZ_PER_S * TICK
        frecuencia += max(-step, min(step, target - frecuencia))

        falla = 0 if comunicacion_ok else 1
        holding.setValues(
            10, [marcha, 1 if cmd_auto else 0, sp_x10, vel_x10, int(round(frecuencia * 10)), falla]
        )
        time.sleep(TICK)


if __name__ == "__main__":
    threading.Thread(target=plc_cycle, daemon=True).start()
    log.info("PLC de prueba escuchando Modbus TCP en 0.0.0.0:%d", PORT)
    StartTcpServer(context=context, address=("0.0.0.0", PORT))
