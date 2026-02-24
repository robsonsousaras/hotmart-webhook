from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, auth, firestore
import random
import string
import os
import json
from datetime import datetime, timedelta

app = Flask(__name__)

cred_json = os.environ.get("FIREBASE_CREDENTIALS")
cred_dict = json.loads(cred_json)
cred = credentials.Certificate(cred_dict)
firebase_admin.initialize_app(cred)
db = firestore.client()

def gerar_senha(tamanho=10):
    caracteres = string.ascii_letters + string.digits
    return ''.join(random.choice(caracteres) for _ in range(tamanho))

def identificar_plano(nome_produto):
    nome = nome_produto.lower()
    if 'vitalicio' in nome or 'vitalício' in nome or 'lifetime' in nome:
        return 'vitalicio', None
    elif 'anual' in nome or 'annual' in nome or '12 mes' in nome:
        return 'anual', datetime.utcnow() + timedelta(days=365)
    else:
        return 'mensal', datetime.utcnow() + timedelta(days=30)

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
            plano, expiracao = identificar_plano(produto)

            if expiracao is None:
                expiracao = datetime.utcnow() + timedelta(days=36500)  # 100 anos = vitalício

            try:
                usuario = auth.get_user_by_email(email)
            except:
                usuario = auth.create_user(email=email, password=senha)

            db.collection('licenses').document(usuario.uid).set({
                'email': email,
                'nome': nome,
                'produto': produto,
                'plano': plano,
                'ativo': True,
                'deviceId': '',
                'expiracao': expiracao
            })

            return jsonify({'status': 'sucesso', 'plano': plano, 'email': email}), 200

        if evento in ['PURCHASE_CANCELLED', 'PURCHASE_REFUNDED']:
            try:
                usuario = auth.get_user_by_email(email)
                db.collection('licenses').document(usuario.uid).update({'ativo': False})
            except:
                pass
            return jsonify({'status': 'licenca desativada'}), 200

        return jsonify({'status': 'ignorado'}), 200

    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/')
def index():
    return 'API ShopeeZPLPrinter rodando!', 200

if __name__ == '__main__':
    app.run()
