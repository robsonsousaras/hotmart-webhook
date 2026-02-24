from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, auth, firestore
import random
import string
import os
import json

app = Flask(__name__)

# Inicializa Firebase
cred_json = os.environ.get("FIREBASE_CREDENTIALS")
cred_dict = json.loads(cred_json)
cred = credentials.Certificate(cred_dict)
firebase_admin.initialize_app(cred)
db = firestore.client()

def gerar_senha(tamanho=10):
    caracteres = string.ascii_letters + string.digits
    return ''.join(random.choice(caracteres) for _ in range(tamanho))

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    
    try:
        evento = data['event']
        comprador = data['data']['buyer']
        email = comprador['email']
        nome = comprador['name']
        produto = data['data']['product']['name']
        
        if evento == 'PURCHASE_APPROVED':
            senha = gerar_senha()
            usuario = auth.create_user(email=email, password=senha)
            
            db.collection('licencas').document(usuario.uid).set({
                'nome': nome,
                'email': email,
                'produto': produto,
                'status': 'ativo',
                'uid': usuario.uid
            })
            
            return jsonify({'status': 'sucesso', 'mensagem': f'Usuário {email} criado'}), 200
        
        return jsonify({'status': 'ignorado'}), 200
    
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/')
def index():
    return 'API ShopeeZPLPrinter rodando!', 200

if __name__ == '__main__':
    app.run()
