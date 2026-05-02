class User:
    def __init__(self, id, name, email, password, level, otp=None, otp_expiry=None):
        self.id = id
        self.name = name
        self.email = email
        self.password = password
        self.level = level
        self.otp = otp
        self.otp_expiry = otp_expiry