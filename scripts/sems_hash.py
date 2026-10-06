#!/usr/bin/env python3
"""Genera el valor de ``sems.password_hash`` para config.yaml.

SEMS+ nunca recibe la contraseña en claro, sino base64(md5(contraseña)); el
dashboard puede guardar solo eso. Ojo: el hash sigue permitiendo entrar en
SEMS, así que protege config.yaml igual que una contraseña.

Uso: python3 scripts/sems_hash.py
"""

import base64
import getpass
import hashlib

password = getpass.getpass("Contraseña de SEMS (no se muestra): ")
print(base64.b64encode(hashlib.md5(password.encode()).hexdigest().encode()).decode())
