from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from flask_jwt_extended import JWTManager

mail = Mail()
csrf = CSRFProtect()
jwt = JWTManager()
