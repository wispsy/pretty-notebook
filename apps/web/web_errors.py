"""Application-owned structured input failures."""


class InputErrors(Exception):
    def __init__(self, details):
        self.details = details
        super().__init__('Request input does not match the application schema.')
