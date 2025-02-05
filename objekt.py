from dataclasses import dataclass


@dataclass
class Objekt:
    collection: str
    front_image: str
    back_image: str
    copies: int
    description: str
    transferable: str  # 可傳數量
    percentage: str  # 可傳率

    def __str__(self):
        return f"""Collection: {self.collection}
        Front Image: {self.front_image}
        Back Image: {self.back_image}
        Copies: {self.copies}    
        Description: {self.description}
        Transferable: {self.transferable}
        Percentage: {self.percentage}"""
