"""
CatalogoCuba - Aplicacion de catalogos para pequenos negocios cubanos
Punto de entrada de la aplicacion py4web
"""
from py4web import action

# Importar modulos de la aplicacion
from . import common, models, controllers

# La aplicacion se registra automaticamente al importar los controladores
# El nombre de la app se deriva del nombre de la carpeta: catalogo_cuba
