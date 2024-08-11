class Objekt:
    def __init__(self, collection: str, front_image: str, back_image: str, copies: int, description: str):
        self.collection = collection
        self.front_image = front_image
        self.back_image = back_image
        self.copies = copies
        self.description = description

    def __str__(self):
        return (f"collection: {self.collection}\nFront Image: {self.front_image}\nBack Image: {self.back_image}\n"
                f"Copies: {self.copies}\nDescription: {self.description}")
