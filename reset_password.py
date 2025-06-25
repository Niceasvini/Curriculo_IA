import streamlit as st
from CONFIG.database import AnalyseDataBase

# Instancia o database
database = AnalyseDataBase()
def reset_password_page():
    st.set_page_config(page_title="Redefinição de Senha", page_icon="🔑")

    st.markdown("""
    ## 🔐 Redefinição de Senha
    Insira e confirme sua nova senha para continuar.
    """)

    # Pega os parâmetros da URL
    params = st.experimental_get_query_params()
    access_token = params.get("access_token", [None])[0]

    if not access_token:
        st.error("❌ Token não encontrado. Verifique o link ou solicite um novo.")
        st.stop()

    new_password = st.text_input("Nova Senha", type="password")
    confirm_password = st.text_input("Confirme a nova senha", type="password")

    if st.button("Redefinir senha"):
        if new_password != confirm_password:
            st.error("❌ As senhas não coincidem.")
        elif not new_password:
            st.error("❌ Por favor, insira uma nova senha.")
        else:
            try:
                result = database.supabase.auth.api.update_user(new_password, access_token=access_token)
                if result:
                    st.success("✅ Sua senha foi atualizada com sucesso!")
                    st.markdown("[👉 Voltar para o Login](https://vianaemouracurriculos.streamlit.app/?page=login)")
            except Exception as e:
                st.error(f"❌ Não foi possível redefinir a senha: {e}")
