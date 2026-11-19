# -*- coding: utf-8 -*-
# Reportes de dirección y comerciales (DACSA) · Slyn
# Punto de entrada del módulo: carga los modelos y expone el hook de instalación.
from . import models
from .hooks import post_init_hook
