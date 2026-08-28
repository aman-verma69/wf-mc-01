from backend.tools.cart_tools import add_to_cart, remove_from_cart, get_cart, calculate_total

class CartAgent:
    add_to_cart = staticmethod(add_to_cart)
    remove_from_cart = staticmethod(remove_from_cart)
    get_cart = staticmethod(get_cart)
    calculate_total = staticmethod(calculate_total)
