from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

mail = Mail()
csrf = CSRFProtect()
jwt = JWTManager()
limiter = Limiter(key_func=get_remote_address)
