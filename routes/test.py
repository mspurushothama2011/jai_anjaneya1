import os
from dotenv import load_dotenv

load_dotenv()

print("RAZORPAY_KEY_ID:", os.getenv("RAZORPAY_KEY_ID"))
print("RAZORPAY_KEY_SECRET:", os.getenv("RAZORPAY_KEY_SECRET"))
