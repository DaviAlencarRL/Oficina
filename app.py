from flask import Flask
from dotenv import load_dotenv
import os
import mysql.connector

# carregar variáveis .env
load_dotenv()

# pegar variáveis
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

app = Flask(__name__)

#se conectar ao banco de dados
def conectar():
    conexao = mysql.connector.connect(
        host="localhost",
        user="admin",
        password="1555",
        database="oficina"
    )
    return conexao

#rodar o site
@app.route("/")
def home():
    return "Olá Mundo - Sistema da Oficina"

if __name__ == "__main__":
    app.run(debug=True)