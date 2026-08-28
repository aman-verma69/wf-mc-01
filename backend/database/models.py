from dataclasses import dataclass

@dataclass(frozen=True)
class Product:
    id: str
    name: str
    description: str
    price: int
    stock: int
    category: str
