import streamlit as st
import openai
import requests
import json

SPOTIFY_API_DOC = """
La API de Spotify permite buscar y obtener información de artistas, álbumes, canciones, playlists, etc.
Principales endpoints:
- GET /v1/search?q={query}&type={type}: Busca en Spotify (type: track, album, artist, playlist)
- GET /v1/artists/{id}: Info de un artista
- GET /v1/tracks/{id}: Info de una canción
- GET /v1/albums/{id}: Info de un álbum
- GET /v1/playlists/{id}: Info de una playlist
- GET /v1/artists/{id}/top-tracks: Top canciones de un artista
"""

def clean_llm_json(text):
    # Limpieza robusta del JSON devuelto por el LLM (quita backticks, markdown, etc.)
    text = text.strip()
    # Quita todo antes de la primera llave {
    first_brace = text.find('{')
    if first_brace != -1:
        text = text[first_brace:]
    # Quita todo después de la última llave }
    last_brace = text.rfind('}')
    if last_brace != -1:
        text = text[:last_brace+1]
    # Borra backticks, markdown y saltos de línea sueltos
    text = text.replace("```json", "").replace("```", "").strip()
    return text

class SpotifyAPIExplorer:
    def __init__(self, client_id, client_secret, openai_api_key):
        self.client_id = client_id
        self.client_secret = client_secret
        self.openai_api_key = openai_api_key
        self.access_token = self.get_access_token()

    def get_access_token(self):
        url = 'https://accounts.spotify.com/api/token'
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        data = {'grant_type': 'client_credentials'}
        resp = requests.post(url, headers=headers, data=data, auth=(self.client_id, self.client_secret))
        resp.raise_for_status()
        return resp.json()['access_token']

    def run_query(self, user_query):
        openai.api_key = self.openai_api_key
        prompt = (
            f"{SPOTIFY_API_DOC}\n"
            "Eres un agente que recibe consultas de usuario y las traduce a llamadas HTTP a la API de Spotify. "
            "Para cada consulta de usuario, responde en JSON con los campos: 'endpoint', 'method', 'params'. "
            "Ejemplo de output:\n"
            "{'endpoint': '/v1/search', 'method': 'GET', 'params': {'q': 'Beatles', 'type': 'artist'}}\n\n"
            f"Consulta de usuario: '{user_query}'\n"
            "Output:"
        )
        completion = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0
        )
        response = completion.choices[0].message.content
        response = clean_llm_json(response.replace("'", '"'))
        try:
            api_call = json.loads(response)
        except json.JSONDecodeError:
            st.error(f"Error interpretando la respuesta del LLM: {response}")
            return None
        # Ejecutar llamada real a Spotify API
        url = f"https://api.spotify.com{api_call['endpoint']}"
        headers = {'Authorization': f'Bearer {self.access_token}'}
        params = api_call.get('params', {})
        resp = requests.request(api_call['method'], url, headers=headers, params=params)
        resp.raise_for_status()
        return resp.json()

# --- Interfaz Streamlit ---

st.title("Spotify API Explorer (con LLM)")
client_id = st.text_input("Spotify Client ID")
client_secret = st.text_input("Spotify Client Secret", type="password")
openai_api_key = st.text_input("OpenAI API Key", type="password")
user_query = st.text_input("Pregunta sobre Spotify", "")

if st.button("Buscar") and client_id and client_secret and openai_api_key and user_query:
    explorer = SpotifyAPIExplorer(client_id, client_secret, openai_api_key)
    with st.spinner("Consultando..."):
        try:
            result = explorer.run_query(user_query)
            if result:
                st.json(result)
        except Exception as e:
            st.error(f"Error: {e}")



