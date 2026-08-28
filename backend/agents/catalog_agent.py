from backend.tools.catalog_tools import search_products, get_product, check_inventory

class CatalogAgent:
    search_products = staticmethod(search_products)
    get_product = staticmethod(get_product)
    check_inventory = staticmethod(check_inventory)
