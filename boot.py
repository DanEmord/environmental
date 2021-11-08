# This file is executed on every boot (including wake-boot from deepsleep)
import uos
uos.dupterm(None, 1) # disable REPL on UART(0)

import webrepl
webrepl.start()
