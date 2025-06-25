import streamlit as st
from CONFIG.database import AnalyseDataBase

# Instancia o database
database = AnalyseDataBase()

st.set_page_config(page_title="Redefinição de Senha", page_icon="🔑")

st.markdown("""
## 🔐 Redefinição de Senha
Insira e confirme sua nova senha para continuar.
""")

# ✅ Captura o access_token dos parâmetros de URL
params = st.query_params
access_token = params.get("access_token", None)

if not access_token:
    st.error("❌ Token não encontrado. Verifique o link ou solicite um novo.")
    st.stop()

new_password = st.text_input("Nova Senha", type="password")
confirm_password = st.text_input("Confirme a nova senha", type="password")

if st.button("Redefinir senha"):
    if new_password != confirm_password:
        st.error("❌ As senhas não coincidem.")
    else:
        try:
            result = database.supabase.auth.api.update_user(new_password, access_token=access_token)

            if result:
                st.success("✅ Sua senha foi atualizada com sucesso!")

                st.markdown("""
                👉 [Voltar para o Login](https://vianaemouracurriculos.streamlit.app/)
                """)
                
        except Exception as e:
            st.error(f"❌ Não foi possível redefinir a senha: {e}")