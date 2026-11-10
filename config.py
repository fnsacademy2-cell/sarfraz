import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    BASE_DIR = BASE_DIR
    SECRET_KEY = os.environ.get('SECRET_KEY', 'grocery-mis-secret-key-2026')
    DATABASE_PATH = os.path.join(BASE_DIR, 'grocery_store.db')
    DEBUG = True

