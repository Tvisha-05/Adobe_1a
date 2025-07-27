class Heading:
    def __init__(self, level: str, text: str, page: int):
        self.level = level
        self.text = text
        self.page = page

class Outline:
    def __init__(self, title: str, headings: list):
        self.title = title
        self.headings = headings

    def to_dict(self):
        return {
            "title": self.title,
            "outline": [heading.__dict__ for heading in self.headings]
        }