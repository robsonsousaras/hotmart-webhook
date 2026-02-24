from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, auth, firestore
import random
import string
import os
import json
from datetime import datetime, timedelta
import resend

app = Flask(__name__)

cred_json = os.environ.get("FIREBASE_CREDENTIALS")
cred_dict = json.loads(cred_json)
cred = credentials.Certificate(cred_dict)
firebase_admin.initialize_app(cred)
db = firestore.client()

resend.api_key = os.environ.get("RESEND_API_KEY")

def gerar_senha(tamanho=10):
    caracteres = string.ascii_letters + string.digits
    return ''.join(random.choice(caracteres) for _ in range(tamanho))

def identificar_plano(nome_produto):
    nome = nome_produto.lower()
    if 'vitalicio' in nome or 'vitalício' in nome or 'lifetime' in nome:
        return 'vitalicio', datetime.utcnow() + timedelta(days=36500)
    elif 'anual' in nome or 'annual' in nome or '12 mes' in nome:
        return 'anual', datetime.utcnow() + timedelta(days=365)
    else:
        return 'mensal', datetime.utcnow() + timedelta(days=30)

def enviar_email(destinatario, nome, email, senha, plano):
    try:
        plano_texto = "Vitalício" if plano == "vitalicio" else "Anual" if plano == "anual" else "Mensal"

        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; background: #0d0d0d; color: #e8e8e8; padding: 32px; border-radius: 8px;">
            <h2 style="color: #ff6b1a;">🖨 ShopeeZPLPrinter</h2>
            <p>Olá, <strong>{nome}</strong>! Seu acesso foi liberado.</p>
            <div style="background: #1a1a1a; padding: 16px; border-radius: 6px; margin: 24px 0;">
                <p style="margin: 4px 0;"><strong>Plano:</strong> {plano_texto}</p>
                <p style="margin: 4px 0;"><strong>E-mail:</strong> {email}</p>
                <p style="margin: 4px 0;"><strong>Senha:</strong> <span style="color: #ff6b1a; font-size: 18px;">{senha}</span></p>
            </div>
            <p>Baixe o programa, abra e faça login com essas credenciais.</p>
            <p style="color: #666; font-size: 12px;">Guarde sua senha em um local seguro.</p>
        </div>
        """

        resend.Emails.send({
            "from": "ShopeeZPLPrinter <onboarding@resend.dev>",
            "to": destinatario,
            "subject": "Seu acesso ao ShopeeZPLPrinter",
            "html": html
        })

        return True
    except Exception as e:
        print(f"Erro ao enviar email: {e}")
        return False

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

            try:
                usuario = auth.get_user_by_email(email)
                auth.update_user(usuario.uid, password=senha)
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

            enviar_email(email, nome, email, senha, plano)

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
